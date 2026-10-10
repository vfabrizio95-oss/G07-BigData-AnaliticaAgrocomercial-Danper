from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, trim, upper
from pyspark.sql.types import (
    StructType, StructField, StringType,
    IntegerType, DoubleType
)

import extractor_agricola as extractor


BRONZE = "/danper/bronze/produccion"
SILVER = "/danper/silver/produccion"


def main():
    spark = (
        SparkSession.builder
        .appName("Danper_Transformacion_Silver")
        .master("local[2]")
        .getOrCreate()
    )

    try:
        # 1. Recuperar temporalmente los Excel desde HDFS Bronze.
        with TemporaryDirectory() as temporal:
            ruta_temporal = Path(temporal)

            subprocess.run(
                ["hdfs", "dfs", "-get", f"{BRONZE}/*.xlsx", temporal],
                check=True
            )

            # 2. Reutilizar la extracción desarrollada por Fao.
            extractor.RUTA_DATOS = ruta_temporal
            datos = extractor.extraer_datos_agricolas()

        print("Registros extraídos desde Bronze:", len(datos))

        if datos.empty:
            raise ValueError("No se encontraron registros para Silver")

        # 3. Definir los tipos de datos explícitamente.
        esquema = StructType([
            StructField("provincia", StringType(), False),
            StructField("distrito", StringType(), False),
            StructField("codigo_cultivo", StringType(), False),
            StructField("cultivo", StringType(), False),
            StructField("variable", StringType(), False),
            StructField("columna_origen", IntegerType(), False),
            StructField("mes_origen", StringType(), False),
            StructField("valor", DoubleType(), False),
            StructField("archivo_origen", StringType(), False)
        ])

        registros = [
            (
                str(fila.provincia),
                str(fila.distrito),
                str(fila.codigo_cultivo),
                str(fila.cultivo),
                str(fila.variable),
                int(fila.columna_origen),
                str(fila.mes_origen),
                float(fila.valor),
                str(fila.archivo_origen)
            )
            for fila in datos.itertuples(index=False)
        ]

        df = spark.createDataFrame(registros, schema=esquema)

        # 4. Estandarizar campos de texto.
        campos_texto = [
            "provincia",
            "distrito",
            "codigo_cultivo",
            "cultivo",
            "variable",
            "mes_origen",
            "archivo_origen"
        ]

        for campo in campos_texto:
            df = df.withColumn(campo, trim(col(campo)))

        for campo in ["provincia", "distrito", "cultivo", "mes_origen"]:
            df = df.withColumn(campo, upper(col(campo)))

        # 5. Conservar la columna que identifica cada período.
        df = df.withColumn(
            "posicion_mensual",
            col("columna_origen") - 3
        )

        # 6. Validaciones iniciales.
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
            col("valor").isNull() |
            col("cultivo").isNull() |
            col("variable").isNull()
        ).count()

        print("===== CONTROL DE CALIDAD SILVER =====")
        print("Registros:", total)
        print("Duplicados por clave:", duplicados)
        print("Nulos críticos:", nulos)
        print("Provincias:", df.select("provincia").distinct().count())
        print("Cultivos:", df.select("cultivo").distinct().count())

        if duplicados > 0 or nulos > 0:
            raise ValueError(
                "Se detectaron problemas de calidad. "
                "No se escribirá Silver."
            )

        # 7. Escribir en formato Parquet dentro de HDFS.
        df.write.mode("overwrite").parquet(SILVER)

        print("Silver generado correctamente:", SILVER)
        df.show(5, truncate=False)

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
