"""Publica Gold (HDFS, Parquet) en PostgreSQL para el dashboard.

Spark lee las 26 tablas de Gold y las publica en el esquema DANPER_PG_SCHEMA
(por defecto "gold") con el patrón Write-Audit-Publish, igual que Gold:

1. Write: escribe cada tabla por JDBC en <esquema>_staging (cada partición de
   Spark inserta en paralelo).
2. Audit: comprueba que cada tabla de staging tenga las filas leídas de Gold.
3. Publish: en UNA transacción reemplaza cada tabla de <esquema> por su versión
   de staging, devuelve SELECT a los roles lectores (por ejemplo
   grafana_lector) y registra la publicación en <esquema>.control_publicacion.

El dashboard nunca ve una tabla vacía ni a medio cargar: ve la versión anterior
completa o la nueva completa. Si algo falla, la transacción se deshace y
<esquema> queda como estaba.

También publica las tablas del modelo (scripts/modelo_abastecimiento.py) si
ya existen en Gold; si no, las omite con un aviso.

Uso:
    spark-submit --jars ~/proyecto_danper/jars/postgresql-42.7.4.jar \
        scripts/publicar_postgres.py
    (o con python: el driver se agrega solo desde DANPER_PG_JAR)
"""
from datetime import datetime
import argparse
import time

from pyspark.sql import SparkSession

import config
from procesamiento_gold import EXPECTED

DRIVER = "org.postgresql.Driver"
# Tablas que escribe scripts/modelo_abastecimiento.py (opcionales).
TABLAS_MODELO = ["ml_prediccion_ingreso", "ml_metricas_modelo", "ml_plan_ingreso"]


def crear_spark():
    if not config.PG_JAR.is_file():
        raise FileNotFoundError(f"No se encontró el driver JDBC: {config.PG_JAR}")
    spark = (
        SparkSession.builder
        .appName("Danper_Publicar_PostgreSQL")
        .config(map=config.SPARK_CONF)
        .config("spark.jars", str(config.PG_JAR))
        # El driver tambien lo usa directamente (CREATE SCHEMA).
        .config("spark.driver.extraClassPath", str(config.PG_JAR))
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def conectar(spark, propiedades):
    """Conexión JDBC directa desde el driver de Spark."""
    jvm = spark._jvm
    jvm.java.lang.Class.forName(DRIVER)
    props = jvm.java.util.Properties()
    for clave, valor in propiedades.items():
        props.setProperty(clave, valor)
    return jvm.java.sql.DriverManager.getConnection(config.PG_URL, props)


def consultar(conexion, sentencia, *parametros):
    """Ejecuta una consulta y devuelve la primera columna de cada fila."""
    st = conexion.prepareStatement(sentencia)
    for i, valor in enumerate(parametros, 1):
        st.setString(i, valor)
    rs = st.executeQuery()
    filas = []
    while rs.next():
        filas.append(rs.getString(1))
    st.close()
    return filas


def lectores(conexion, esquema):
    """Roles (distintos del dueño) con USAGE sobre el esquema: los lectores."""
    return consultar(conexion, """
        SELECT DISTINCT a.grantee::regrole::text
        FROM pg_namespace n, aclexplode(n.nspacl) a
        WHERE n.nspname = ? AND a.privilege_type = 'USAGE'
          AND a.grantee <> n.nspowner AND a.grantee <> 0""", esquema)


def publicar(conexion, esquema, staging, registro):
    """Reemplaza las tablas de `esquema` por las de `staging` en una transacción."""
    roles = lectores(conexion, esquema)
    conexion.setAutoCommit(False)
    try:
        st = conexion.createStatement()
        for nombre, _, _ in registro:
            existe = consultar(conexion, "SELECT to_regclass(?)::text",
                               f'"{esquema}"."{nombre}"')[0]
            if existe:
                st.execute(f'ALTER TABLE "{esquema}"."{nombre}" RENAME TO "{nombre}__anterior"')
            st.execute(f'ALTER TABLE "{staging}"."{nombre}" SET SCHEMA "{esquema}"')
            if existe:
                st.execute(f'DROP TABLE "{esquema}"."{nombre}__anterior"')
            for rol in roles:
                st.execute(f'GRANT SELECT ON "{esquema}"."{nombre}" TO {rol}')
        st.execute(f'CREATE TABLE IF NOT EXISTS "{esquema}".control_publicacion '
                   "(tabla text, filas bigint, publicado_en timestamp)")
        ins = conexion.prepareStatement(
            f'INSERT INTO "{esquema}".control_publicacion VALUES (?, ?, ?::timestamp)')
        for nombre, filas, momento in registro:
            ins.setString(1, nombre)
            ins.setLong(2, filas)
            ins.setString(3, momento)
            ins.addBatch()
        ins.executeBatch()
        conexion.commit()
        return roles
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.setAutoCommit(True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tablas", nargs="+", choices=list(EXPECTED) + TABLAS_MODELO,
                    help="Publicar solo estas tablas (por defecto, las 26 y las del modelo)")
    args = ap.parse_args()

    propiedades = {
        "user": config.PG_USER,
        "password": config.pg_password(),
        "driver": DRIVER,
    }
    esquema = config.PG_SCHEMA
    gold = config.hdfs(config.GOLD)

    spark = crear_spark()
    try:
        if args.tablas:
            tablas = args.tablas
        else:
            jvm = spark._jvm
            fs = jvm.org.apache.hadoop.fs.FileSystem.get(
                jvm.java.net.URI(config.HDFS_URI), spark._jsc.hadoopConfiguration())
            tablas = list(EXPECTED)
            for nombre in TABLAS_MODELO:
                if fs.exists(jvm.org.apache.hadoop.fs.Path(f"{config.GOLD}/{nombre}")):
                    tablas.append(nombre)
                else:
                    print(f"Aviso: {nombre} no existe en Gold "
                          "(ejecute scripts/modelo_abastecimiento.py); se omite")
        staging = f"{esquema}_staging"
        conexion = conectar(spark, propiedades)
        st = conexion.createStatement()
        st.execute(f'CREATE SCHEMA IF NOT EXISTS "{esquema}"')
        st.execute(f'CREATE SCHEMA IF NOT EXISTS "{staging}"')
        print("===== PUBLICAR GOLD EN POSTGRESQL =====")
        print("Destino:", config.PG_URL, "esquema", esquema, "(vía", staging + ")")

        inicio = time.time()
        momento = datetime.now().isoformat(timespec="seconds")
        registro = []

        # 1. Write: cada tabla a staging (se recrea; el esquema publicado no se toca).
        for i, nombre in enumerate(tablas, 1):
            df = spark.read.parquet(f"{gold}/{nombre}")
            filas = df.count()
            (
                df.write.mode("overwrite")
                .option("batchsize", "5000")
                .jdbc(config.PG_URL, f'"{staging}"."{nombre}"', properties=propiedades)
            )
            registro.append((nombre, filas, momento))
            print(f"[{i:02d}/{len(tablas)}] {nombre}: {filas} filas en staging", flush=True)

        # 2. Audit: las filas de staging deben coincidir con las de Gold.
        for nombre, filas, _ in registro:
            en_staging = int(consultar(conexion, f'SELECT count(*) FROM "{staging}"."{nombre}"')[0])
            if en_staging != filas:
                raise RuntimeError(f"{nombre}: {en_staging} filas en staging, {filas} en Gold")
        print(f"Auditoría: {len(registro)} tablas con las mismas filas que Gold")

        # 3. Publish: intercambio atómico y registro de la publicación.
        roles = publicar(conexion, esquema, staging, registro)
        conexion.close()
        print(f"Publicado en una transacción; SELECT para: {', '.join(roles) or '(ningún lector)'}")
        print(f"PUBLICACION COMPLETA: {len(tablas)} tablas en {time.time() - inicio:.1f} s")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
