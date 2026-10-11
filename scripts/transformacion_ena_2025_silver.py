
from pathlib import Path
from tempfile import TemporaryDirectory
import argparse
import math
import subprocess
import time
import unicodedata

import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql.types import (
    StructType, StructField,
    StringType, DoubleType, IntegerType
)


BRONZE = "/danper/bronze/costos/ena_2025/ENA_2025"
SILVER = "/danper/silver/ena_2025"

COMUNES = [
    "ANIO", "NSEGM", "ID_PROD", "UA",
    "NOMBREDD", "NOMBREPV", "NOMBREDI"
]

CONFIG = {
    "produccion": {
        "modulo": "1035-Modulo1895",
        "archivo": "03_CAP200AB.csv",
        "cultivo": "P204_NOM",
        "esperados": 49,
        "clave": [
            "ANIO", "NSEGM", "ID_PROD", "UA",
            "P105", "P105_DIB", "P147",
            "P203", "P204_COD", "P205_N"
        ],
        "texto": [
            "FACTOR_PRODUCTOR",
            "P105", "P105_DIB", "P147",
            "P203", "P204_NOM", "P204_COD",
            "P205_N"
        ],
        "numeros": [
            "P217_SUP_ha",
            "P219_EQUIV_KG",
            "P220_1_VAL",
            "P220_1_PRE_KG",
            "P220_2_VAL",
            "P220_2_PRE_KG"
        ]
    },
    "insumos": {
        "modulo": "1035-Modulo1899",
        "archivo": "07_CAP200E.csv",
        "cultivo": "P234_NOM",
        "esperados": 23,
        "clave": [
            "ANIO", "NSEGM", "ID_PROD", "UA",
            "P234_N", "P234_COD"
        ],
        "texto": [
            "FACTOR_PRODUCTOR",
            "P234_N", "P234_NOM", "P234_COD"
        ],
        "numeros": [
            "P235_VAL",
            "P235_PRE_KG",
            "P237_VAL",
            "P237_PRE_KG"
        ]
    },
    "uso_tierra": {
        "modulo": "1035-Modulo1893",
        "archivo": "01_USOSTIERRA.csv",
        "cultivo": "P115_NOM",
        "esperados": 77,
        "clave": [
            "ANIO", "NSEGM", "ID_PROD", "UA",
            "P105", "P105_DIB",
            "P115_LOTE", "P115",
            "P115_COD", "P116_COD"
        ],
        "texto": [
            "FACTOR_SUPERFICIE",
            "P105", "P105_DIB",
            "P115_LOTE", "P115",
            "P115_NOM", "P115_COD",
            "P116_NOM", "P116_COD"
        ],
        "numeros": [
            "P117_SUP_ha"
        ]
    }
}


def ejecutar(comando):
    return subprocess.run(
        comando,
        capture_output=True,
        text=True,
        check=False
    )


def normalizar(valor):
    if pd.isna(valor):
        return ""

    texto = str(valor).strip().upper()

    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def texto_limpio(valor):
    if pd.isna(valor):
        return None

    texto = str(valor).strip()
    return texto if texto else None


def numero_limpio(valor, campo, fila):
    texto = texto_limpio(valor)

    if texto is None:
        return None

    try:
        numero = float(texto)
    except ValueError:
        raise ValueError(
            f"Valor no numerico en {campo}, fila {fila}: {texto}"
        )

    if not math.isfinite(numero):
        raise ValueError(
            f"Valor no finito en {campo}, fila {fila}"
        )

    if numero < 0:
        raise ValueError(
            f"Valor negativo en {campo}, fila {fila}"
        )

    return numero


def columnas_salida(config):
    columnas = []

    for nombre in COMUNES + config["texto"]:
        if nombre not in columnas:
            columnas.append(nombre)

    return columnas


def extraer(nombre_tabla, config, archivo, ruta_bronze):
    print("Leyendo CSV...", flush=True)

    df = pd.read_csv(
        archivo,
        dtype=str,
        encoding="utf-8-sig",
        low_memory=False
    )

    requeridas = set(
        COMUNES
        + config["clave"]
        + config["texto"]
        + config["numeros"]
    )

    faltantes = sorted(requeridas - set(df.columns))

    if faltantes:
        raise ValueError(
            f"Faltan columnas en {config['archivo']}: {faltantes}"
        )

    print("Filas de origen:", len(df), flush=True)

    departamento = df["NOMBREDD"].map(normalizar)
    cultivos = df[config["cultivo"]].map(normalizar)

    mascara = (
        (departamento == "LA LIBERTAD")
        & cultivos.isin(["ESPARRAGO", "ALCACHOFA"])
    )

    seleccion = df.loc[mascara].copy()

    print("Filas seleccionadas:", len(seleccion), flush=True)

    repetidas = seleccion.duplicated(
        subset=config["clave"],
        keep=False
    )

    if repetidas.any():
        raise ValueError(
            f"Claves repetidas en {nombre_tabla}: "
            f"{int(repetidas.sum())}"
        )

    if len(seleccion) != config["esperados"]:
        raise ValueError(
            f"Cantidad inesperada en {nombre_tabla}: "
            f"{len(seleccion)}; "
            f"esperados {config['esperados']}"
        )

    textos = columnas_salida(config)
    numeros = config["numeros"]

    registros = []

    for indice, fila in seleccion.iterrows():
        fila_csv = int(indice) + 2
        registro = {}

        for campo in textos:
            registro[campo] = texto_limpio(fila[campo])

        for campo in numeros:
            registro[campo] = numero_limpio(
                fila[campo], campo, fila_csv
            )

        registro["cultivo_normalizado"] = normalizar(
            fila[config["cultivo"]]
        )
        registro["archivo_origen"] = config["archivo"]
        registro["ruta_bronze"] = ruta_bronze
        registro["fila_csv"] = fila_csv

        registros.append(registro)

    print(
        "Claves unicas:",
        len(seleccion),
        flush=True
    )

    for campo in numeros:
        disponibles = sum(
            fila[campo] is not None
            for fila in registros
        )
        print(
            f"  {campo}: {disponibles} disponibles, "
            f"{len(registros) - disponibles} nulos",
            flush=True
        )

    return registros, textos, numeros


def crear_dataframe(spark, registros, textos, numeros):
    esquema = []

    for campo in textos:
        esquema.append(
            StructField(campo, StringType(), True)
        )

    for campo in numeros:
        esquema.append(
            StructField(campo, DoubleType(), True)
        )

    for campo in [
        "cultivo_normalizado",
        "archivo_origen",
        "ruta_bronze"
    ]:
        esquema.append(
            StructField(campo, StringType(), False)
        )

    esquema.append(
        StructField("fila_csv", IntegerType(), False)
    )

    schema = StructType(esquema)
    orden = [campo.name for campo in schema.fields]

    filas = [
        tuple(registro[campo] for campo in orden)
        for registro in registros
    ]

    return spark.createDataFrame(
        filas,
        schema=schema
    )


def verificar_destinos():
    print("\n===== SEGURIDAD DE DESTINOS =====", flush=True)

    for nombre in CONFIG:
        ruta = f"{SILVER}/{nombre}"
        proceso = ejecutar([
            "hdfs", "dfs", "-test", "-e", ruta
        ])

        if proceso.returncode == 0:
            raise RuntimeError(
                f"DESTINO EXISTENTE: {ruta}. "
                "No se sobrescribira."
            )

        if proceso.returncode != 1:
            raise RuntimeError(
                f"No se pudo comprobar {ruta}: "
                f"{proceso.stderr}"
            )

        print("Destino libre:", ruta, flush=True)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--ejecutar",
        action="store_true",
        help="Escribir tablas en HDFS Silver"
    )

    args = parser.parse_args()
    inicio = time.time()

    print("===== ENA 2025 - TRANSFORMACION SILVER =====")
    print(
        "MODO:",
        "ESCRITURA" if args.ejecutar else "SOLO VALIDACION",
        flush=True
    )

    if args.ejecutar:
        verificar_destinos()

    resultados = {}

    with TemporaryDirectory() as temporal:
        for i, (nombre, config) in enumerate(
            CONFIG.items(), 1
        ):
            print(
                f"\n[{i}/3] Procesando {nombre}",
                flush=True
            )

            ruta_bronze = (
                f"{BRONZE}/{config['modulo']}/"
                f"{config['archivo']}"
            )

            local = (
                Path(temporal) / config["archivo"]
            )

            print("Origen:", ruta_bronze, flush=True)

            subprocess.run(
                [
                    "hdfs", "dfs", "-get",
                    ruta_bronze, str(local)
                ],
                check=True
            )

            resultados[nombre] = extraer(
                nombre,
                config,
                local,
                ruta_bronze
            )

            print(
                f"PROGRESO EXTRACCION: {i / 3 * 100:.0f}%",
                flush=True
            )

    print("\n===== INICIANDO PYSPARK =====", flush=True)

    spark = (
        SparkSession.builder
        .appName("Danper_ENA_2025_Silver")
        .master("local[2]")
        .getOrCreate()
    )

    try:
        spark.sparkContext.setLogLevel("ERROR")

        for i, (nombre, contenido) in enumerate(
            resultados.items(), 1
        ):
            registros, textos, numeros = contenido

            df = crear_dataframe(
                spark, registros, textos, numeros
            )

            cantidad = df.count()

            if cantidad != CONFIG[nombre]["esperados"]:
                raise ValueError(
                    f"Cantidad distinta en Spark: {nombre}"
                )

            print(
                f"\n[{i}/3] TABLA: {nombre}",
                flush=True
            )
            print("Registros Spark:", cantidad, flush=True)

            df.groupBy(
                "cultivo_normalizado"
            ).count().show()

            if args.ejecutar:
                destino = f"{SILVER}/{nombre}"

                print(
                    "Escribiendo:", destino,
                    flush=True
                )

                df.write.mode(
                    "errorifexists"
                ).parquet(destino)

                print(
                    "Registros escritos:",
                    spark.read.parquet(destino).count(),
                    flush=True
                )

            print(
                f"PROGRESO SPARK: {i / 3 * 100:.0f}%",
                flush=True
            )

        if args.ejecutar:
            print(
                "\nTablas Silver generadas correctamente.",
                flush=True
            )
        else:
            print(
                "\nVALIDACION COMPLETADA."
                "\nNo se modifico HDFS Silver.",
                flush=True
            )

    finally:
        spark.stop()
        print(
            "\nTiempo total:",
            round(time.time() - inicio, 2),
            "segundos",
            flush=True
        )


if __name__ == "__main__":
    main()
