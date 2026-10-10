from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, isnan, count, when,
    min as spark_min, max as spark_max,
    sum as spark_sum
)

RUTA = "/danper/silver/produccion/"

spark = (
    SparkSession.builder
    .appName("Danper_Calidad_Silver")
    .master("local[2]")
    .getOrCreate()
)

try:
    df = spark.read.parquet(RUTA)

    print("\n===== CALIDAD DE DATOS SILVER =====")

    total = df.count()

    claves = [
        "provincia",
        "distrito",
        "codigo_cultivo",
        "variable",
        "columna_origen",
        "archivo_origen"
    ]

    duplicados = total - df.select(*claves).distinct().count()

    nulos = df.filter(
        col("valor").isNull() | isnan("valor")
    ).count()

    negativos = df.filter(col("valor") < 0).count()

    ceros = df.filter(col("valor") == 0).count()

    print("Total registros:", total)
    print("Duplicados:", duplicados)
    print("Valores nulos o NaN:", nulos)
    print("Valores negativos:", negativos)
    print("Valores iguales a cero:", ceros)
    print("Provincias:", df.select("provincia").distinct().count())
    print("Cultivos:", df.select("cultivo").distinct().count())

    print("\n===== CALIDAD POR VARIABLE =====")

    df.groupBy("variable").agg(
        count("*").alias("registros"),
        spark_min("valor").alias("minimo"),
        spark_max("valor").alias("maximo"),
        spark_sum(
            when(col("valor") == 0, 1).otherwise(0)
        ).alias("ceros")
    ).orderBy("variable").show(truncate=False)

    print("\n===== CULTIVOS PRINCIPALES =====")

    objetivos = df.filter(
        col("cultivo").isin("ESPARRAGO", "ALCACHOFA")
    )

    objetivos.groupBy(
        "cultivo", "variable"
    ).count().orderBy(
        "cultivo", "variable"
    ).show(30, truncate=False)

    print("\n===== RESULTADO DEL CONTROL =====")

    if duplicados == 0 and nulos == 0 and negativos == 0:
        print("CONTROLES BASICOS SUPERADOS")
    else:
        print("SE DETECTARON INCIDENCIAS DE CALIDAD")
        raise ValueError("Controles basicos no superados")

finally:
    spark.stop()
