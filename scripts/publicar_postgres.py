"""Publica Gold (HDFS, Parquet) en PostgreSQL para el dashboard.

Spark lee las 26 tablas de Gold y las escribe por JDBC en el esquema
DANPER_PG_SCHEMA (por defecto "gold"). Cada tabla se vacía y se vuelve a cargar
(overwrite + truncate), así se conserva su definición y las vistas o
conexiones del dashboard no se rompen. Al final registra la publicación en
<esquema>.control_publicacion (tabla, filas y fecha), que el dashboard puede
usar para mostrar la última actualización.

Uso:
    spark-submit --jars ~/proyecto_danper/jars/postgresql-42.7.4.jar \
        scripts/publicar_postgres.py
    (o con python: el driver se agrega solo desde DANPER_PG_JAR)
"""
from datetime import datetime
import argparse
import time

from pyspark.sql import SparkSession, functions as F

import config
from procesamiento_gold import EXPECTED

DRIVER = "org.postgresql.Driver"


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


def ejecutar_sql(spark, sentencia, propiedades):
    """Ejecuta una sentencia SQL directa (crear el esquema)."""
    jvm = spark._jvm
    jvm.java.lang.Class.forName(DRIVER)
    props = jvm.java.util.Properties()
    for clave, valor in propiedades.items():
        props.setProperty(clave, valor)
    conexion = jvm.java.sql.DriverManager.getConnection(config.PG_URL, props)
    try:
        conexion.createStatement().execute(sentencia)
    finally:
        conexion.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tablas", nargs="+", choices=list(EXPECTED),
                    help="Publicar solo estas tablas (por defecto, las 26)")
    args = ap.parse_args()
    tablas = args.tablas or list(EXPECTED)

    propiedades = {
        "user": config.PG_USER,
        "password": config.pg_password(),
        "driver": DRIVER,
    }
    esquema = config.PG_SCHEMA
    gold = config.hdfs(config.GOLD)

    spark = crear_spark()
    try:
        ejecutar_sql(spark, f'CREATE SCHEMA IF NOT EXISTS "{esquema}"', propiedades)
        print(f"===== PUBLICAR GOLD EN POSTGRESQL =====")
        print("Destino:", config.PG_URL, "esquema", esquema)

        inicio = time.time()
        momento = datetime.now().isoformat(timespec="seconds")
        registro = []

        for i, nombre in enumerate(tablas, 1):
            df = spark.read.parquet(f"{gold}/{nombre}")
            filas = df.count()
            (
                df.write.mode("overwrite")
                .option("truncate", "true")
                .jdbc(config.PG_URL, f'"{esquema}"."{nombre}"', properties=propiedades)
            )
            registro.append((nombre, filas, momento))
            print(f"[{i:02d}/{len(tablas)}] {nombre}: {filas} filas", flush=True)

        (
            spark.createDataFrame(registro, "tabla string, filas long, publicado_en string")
            .withColumn("publicado_en", F.to_timestamp("publicado_en"))
            .write.mode("append")
            .jdbc(config.PG_URL, f'"{esquema}"."control_publicacion"', properties=propiedades)
        )

        print(f"PUBLICACION COMPLETA: {len(tablas)} tablas en {time.time() - inicio:.1f} s")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
