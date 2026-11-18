"""Configuración central del pipeline Danper.

Todos los scripts toman de aquí las rutas y la conexión. Para otro entorno
(por ejemplo, el cluster en AWS) se cambian variables de entorno, no código:

    DANPER_HDFS_URI      URI del NameNode            (por defecto hdfs://localhost:9000)
    DANPER_HDFS_BASE     Carpeta raíz en HDFS        (por defecto /danper)
    DANPER_DATASETS      Carpeta local de datasets   (por defecto ~/proyecto_danper/datasets)
    DANPER_SPARK_MASTER  Master de Spark, opcional   (local[*], yarn, spark://...)

Si DANPER_SPARK_MASTER no se define, el master lo decide spark-submit
(--master); al ejecutar con `python` PySpark usa local[*].
"""
import os
from pathlib import Path

HDFS_URI = os.environ.get("DANPER_HDFS_URI", "hdfs://localhost:9000").rstrip("/")
HDFS_BASE = "/" + os.environ.get("DANPER_HDFS_BASE", "/danper").strip("/")
DATASETS = Path(
    os.environ.get("DANPER_DATASETS", Path.home() / "proyecto_danper" / "datasets")
).expanduser()
SPARK_MASTER = os.environ.get("DANPER_SPARK_MASTER") or None

BRONZE = f"{HDFS_BASE}/bronze"
SILVER = f"{HDFS_BASE}/silver"
GOLD = f"{HDFS_BASE}/gold"
CALIDAD = f"{HDFS_BASE}/calidad"
PRUEBAS_ESCALABILIDAD = f"{HDFS_BASE}/pruebas_escalabilidad"

# Configuración que se pasa a SparkSession.builder.config(map=SPARK_CONF)
SPARK_CONF = {"spark.hadoop.fs.defaultFS": HDFS_URI}
if SPARK_MASTER:
    SPARK_CONF["spark.master"] = SPARK_MASTER


# PostgreSQL (capa de consumo de Gold)
#   DANPER_PG_URL       jdbc:postgresql://localhost:5432/danper
#   DANPER_PG_USER      usuario de la base de datos (por defecto, el del sistema)
#   DANPER_PG_PASSWORD  contraseña; si no se define se busca en ~/.pgpass
#   DANPER_PG_SCHEMA    esquema donde se publica Gold (por defecto gold)
#   DANPER_PG_JAR       driver JDBC de PostgreSQL
PG_URL = os.environ.get("DANPER_PG_URL", "jdbc:postgresql://localhost:5432/danper")
PG_USER = os.environ.get("DANPER_PG_USER", os.environ.get("USER", "postgres"))
PG_SCHEMA = os.environ.get("DANPER_PG_SCHEMA", "gold")
PG_JAR = Path(
    os.environ.get(
        "DANPER_PG_JAR",
        Path.home() / "proyecto_danper" / "jars" / "postgresql-42.7.4.jar",
    )
).expanduser()


def pg_password():
    """Contraseña de PostgreSQL: variable DANPER_PG_PASSWORD o ~/.pgpass."""
    if os.environ.get("DANPER_PG_PASSWORD"):
        return os.environ["DANPER_PG_PASSWORD"]
    pgpass = Path(os.environ.get("PGPASSFILE", Path.home() / ".pgpass"))
    sin_prefijo = PG_URL.split("//", 1)[-1]
    servidor, _, base = sin_prefijo.partition("/")
    host, _, puerto = servidor.partition(":")
    buscado = [host, puerto or "5432", base.split("?")[0], PG_USER]
    if pgpass.is_file():
        for linea in pgpass.read_text().splitlines():
            campos = linea.split(":", 4)
            if len(campos) == 5 and all(
                c in ("*", b) for c, b in zip(campos[:4], buscado)
            ):
                return campos[4]
    raise RuntimeError(
        "Falta la contraseña de PostgreSQL: defina DANPER_PG_PASSWORD "
        "o agregue una línea en ~/.pgpass"
    )


def hdfs(ruta):
    """Devuelve la ruta HDFS completa (con URI) de una ruta absoluta."""
    return f"{HDFS_URI}{ruta}"
