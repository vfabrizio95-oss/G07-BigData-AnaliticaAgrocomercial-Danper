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


def hdfs(ruta):
    """Devuelve la ruta HDFS completa (con URI) de una ruta absoluta."""
    return f"{HDFS_URI}{ruta}"
