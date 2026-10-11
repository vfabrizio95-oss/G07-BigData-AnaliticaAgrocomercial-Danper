from pathlib import Path
from tempfile import TemporaryDirectory
import argparse
import subprocess

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    trim,
    upper,
    when,
    lit,
    concat_ws,
    lpad,
    to_date
)
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    IntegerType,
    DoubleType
)

import extractor_agricola as extractor


# ==========================================
# CONFIGURACION
# ==========================================

BRONZE = "/danper/bronze/produccion"
SILVER = "/danper/silver/produccion"

MESES = {
    "ENE": 1,
    "FEB": 2,
    "MAR": 3,
    "ABR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AGO": 8,
    "SET": 9,
    "OCT": 10,
    "NOV": 11,
    "DIC": 12
}


# ==========================================
# CREAR SESION SPARK
# ==========================================

def crear_spark():
    spark = (
        SparkSession.builder
        .appName("Danper_Produccion_Silver")
        .master("local[2]")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")

    return spark


# ==========================================
# EXTRAER EXCEL DESDE HDFS BRONZE
# ==========================================

def extraer_desde_bronze():
    with TemporaryDirectory() as temporal:
        ruta_temporal = Path(temporal)

        subprocess.run(
            [
                "hdfs",
                "dfs",
                "-get",
                f"{BRONZE}/*.xlsx",
                temporal
            ],
            check=True
        )

        archivos = list(ruta_temporal.glob("*.xlsx"))

        print("Archivos Excel recuperados:", len(archivos))

        if len(archivos) != 12:
            raise ValueError(
                "Se esperaban exactamente 12 archivos "
                "provinciales en Bronze."
            )

        datos = extractor.extraer_datos_agricolas(
            ruta_datos=ruta_temporal
        )

    if datos.empty:
        raise ValueError(
            "No se encontraron registros agrícolas."
        )

    print("Registros extraídos desde Bronze:", len(datos))

    return datos


# ==========================================
# DEFINIR ESQUEMA
# ==========================================

def crear_dataframe(spark, datos):
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

    # Repartir los registros entre particiones.
    rdd = spark.sparkContext.parallelize(
        registros,
        numSlices=4
    )

    return spark.createDataFrame(rdd, schema=esquema)


# ==========================================
# LIMPIEZA Y ESTANDARIZACION
# ==========================================

def limpiar_datos(df):
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
        df = df.withColumn(
            campo,
            trim(col(campo))
        )

    for campo in [
        "provincia",
        "distrito",
        "cultivo",
        "mes_origen"
    ]:
        df = df.withColumn(
            campo,
            upper(col(campo))
        )

    df = df.withColumn(
        "posicion_mensual",
        col("columna_origen") - 3
    )

    return df


# ==========================================
# TRANSFORMACION TEMPORAL
# ==========================================

def agregar_periodos(df):
    # Regla inferida de los archivos 2024-2025:
    # columnas 4-8 = AGO-DIC 2024
    # columnas 9-20 = ENE-DIC 2025

    df = df.withColumn(
        "anio",
        when(
            col("columna_origen").between(4, 8),
            lit(2024)
        ).when(
            col("columna_origen").between(9, 20),
            lit(2025)
        ).otherwise(lit(None).cast("int"))
    )

    expresion_mes = None

    for nombre, numero in MESES.items():
        if expresion_mes is None:
            expresion_mes = when(
                col("mes_origen") == nombre,
                lit(numero)
            )
        else:
            expresion_mes = expresion_mes.when(
                col("mes_origen") == nombre,
                lit(numero)
            )

    df = df.withColumn(
        "mes_numero",
        expresion_mes.otherwise(
            lit(None).cast("int")
        )
    )

    df = df.withColumn(
        "periodo",
        to_date(
            concat_ws(
                "-",
                col("anio").cast("string"),
                lpad(
                    col("mes_numero").cast("string"),
                    2,
                    "0"
                ),
                lit("01")
            ),
            "yyyy-MM-dd"
        )
    )

    return df


# ==========================================
# CONTROLES DE CALIDAD
# ==========================================

def validar_datos(df):
    total = df.count()

    claves = [
        "provincia",
        "distrito",
        "codigo_cultivo",
        "variable",
        "columna_origen",
        "archivo_origen"
    ]

    duplicados = (
        total
        - df.select(*claves).distinct().count()
    )

    nulos = df.filter(
        col("provincia").isNull()
        | col("cultivo").isNull()
        | col("variable").isNull()
        | col("valor").isNull()
    ).count()

    periodos_invalidos = df.filter(
        col("anio").isNull()
        | col("mes_numero").isNull()
        | col("periodo").isNull()
        | (~col("columna_origen").between(4, 20))
    ).count()

    provincias = df.select(
        "provincia"
    ).distinct().count()

    cultivos = df.select(
        "cultivo"
    ).distinct().count()

    archivos = df.select(
        "archivo_origen"
    ).distinct().count()

    print("\n===== CONTROL DE CALIDAD SILVER =====")
    print("Registros:", total)
    print("Duplicados por clave:", duplicados)
    print("Nulos críticos:", nulos)
    print("Períodos inválidos:", periodos_invalidos)
    print("Provincias:", provincias)
    print("Cultivos:", cultivos)
    print("Archivos de origen:", archivos)

    print("\n===== REGISTROS POR AÑO =====")

    df.groupBy("anio").count().orderBy(
        "anio"
    ).show()

    print("\n===== PERÍODOS IDENTIFICADOS =====")

    df.groupBy(
        "anio",
        "mes_numero",
        "periodo"
    ).count().orderBy(
        "periodo"
    ).show(20, truncate=False)

    if duplicados != 0:
        raise ValueError(
            "Se detectaron registros duplicados."
        )

    if nulos != 0:
        raise ValueError(
            "Se detectaron valores nulos críticos."
        )

    if periodos_invalidos != 0:
        raise ValueError(
            "Se detectaron períodos inválidos."
        )

    if provincias != 12 or archivos != 12:
        raise ValueError(
            "No se identificaron las 12 provincias "
            "y los 12 archivos esperados."
        )

    # Validar que los meses correspondan a su
    # posición real en el Excel original.
    meses_por_columna = {
        4: 8, 5: 9, 6: 10, 7: 11, 8: 12,
        9: 1, 10: 2, 11: 3, 12: 4,
        13: 5, 14: 6, 15: 7, 16: 8,
        17: 9, 18: 10, 19: 11, 20: 12
    }

    expresion_esperada = None

    for columna, mes in meses_por_columna.items():
        if expresion_esperada is None:
            expresion_esperada = when(
                col("columna_origen") == columna,
                lit(mes)
            )
        else:
            expresion_esperada = expresion_esperada.when(
                col("columna_origen") == columna,
                lit(mes)
            )

    diferencias = df.filter(
        col("mes_numero") != expresion_esperada.otherwise(
            lit(-1)
        )
    ).count()

    print("Diferencias entre columna y mes:", diferencias)

    if diferencias > 0:
        raise ValueError(
            "La secuencia de meses no coincide "
            "con las columnas originales."
        )

    print("\nRESULTADO: VALIDACIONES SUPERADAS")

    return total


# ==========================================
# PROGRAMA PRINCIPAL
# ==========================================

def main():
    parser = argparse.ArgumentParser(
        description="Producción agrícola Silver Danper"
    )

    parser.add_argument(
        "--ejecutar",
        action="store_true",
        help="Guardar el resultado en HDFS Silver"
    )

    args = parser.parse_args()

    spark = crear_spark()

    try:
        print("===== PRODUCCION AGRICOLA SILVER =====")

        if args.ejecutar:
            print("Modo: TRANSFORMACION Y ESCRITURA")
        else:
            print("Modo: VALIDACION SIN ESCRITURA")

        datos = extraer_desde_bronze()

        df = crear_dataframe(
            spark,
            datos
        )

        df = limpiar_datos(df)
        df = agregar_periodos(df)

        total = validar_datos(df)

        if not args.ejecutar:
            print("\nValidación completada.")
            print("No se modificó HDFS Silver.")
            print("Registros validados:", total)
            return

        print("\n===== ESCRIBIENDO SILVER =====")

        df.write.mode("overwrite").parquet(SILVER)

        print("Silver generado correctamente:", SILVER)

        df.select(
            "provincia",
            "distrito",
            "cultivo",
            "variable",
            "anio",
            "mes_numero",
            "periodo",
            "valor"
        ).show(10, truncate=False)

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
