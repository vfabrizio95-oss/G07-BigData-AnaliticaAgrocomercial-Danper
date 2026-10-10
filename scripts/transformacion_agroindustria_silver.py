from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
import re

import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, count, sum as spark_sum, when
)

from extractor_agroindustria import (
    extraer_agroindustria,
    convertir_numero,
    CUADROS
)

BRONZE = "/danper/bronze/agroindustria"
SILVER = "/danper/silver/agroindustria"
CALIDAD = "/danper/calidad/agroindustria"


def validar_totales(ruta, datos, incidencias):
    resultados = []

    for archivo in sorted(ruta.glob("*.xlsx")):
        cultivo = (
            "ALCACHOFA"
            if "ALCACHOFA" in archivo.name.upper()
            else "ESPARRAGO"
        )

        libro = pd.ExcelFile(archivo)

        for hoja in libro.sheet_names:
            tabla = pd.read_excel(
                archivo, sheet_name=hoja, header=None
            )
            cuadro = None

            for i in range(len(tabla)):
                primera = tabla.iloc[i, 0]
                texto = str(primera).strip().upper()

                match = re.search(
                    r"CUADRO\s*N[°ºo.]?\s*0*(\d+)",
                    texto
                )

                if match:
                    cuadro = int(match.group(1))
                    continue

                if cuadro not in CUADROS:
                    continue

                try:
                    numero = float(primera)
                    if not numero.is_integer():
                        continue
                    anio = int(numero)
                except (ValueError, TypeError):
                    continue

                if not 2010 <= anio <= 2024:
                    continue

                total = convertir_numero(tabla.iloc[i, 1])

                if total is None:
                    continue

                seleccion = datos[
                    (datos["cultivo"] == cultivo)
                    & (datos["cuadro_origen"] == cuadro)
                    & (datos["anio"] == anio)
                ]

                ausentes = incidencias[
                    (incidencias["cultivo"] == cultivo)
                    & (incidencias["cuadro"] == cuadro)
                    & (incidencias["anio"] == anio)
                ]

                suma_meses = float(
                    seleccion["cantidad_t"].sum()
                )

                diferencia = abs(total - suma_meses)
                cantidad_ausentes = len(ausentes)

                if cantidad_ausentes > 0:
                    estado = "INCOMPLETO"
                elif diferencia > 0.01:
                    estado = "DIFERENCIA"
                else:
                    estado = "VALIDADO"

                resultados.append({
                    "cultivo": cultivo,
                    "cuadro_origen": cuadro,
                    "anio": anio,
                    "total_anual_t": float(total),
                    "suma_mensual_t": suma_meses,
                    "diferencia_t": float(diferencia),
                    "meses_ausentes": cantidad_ausentes,
                    "estado": estado,
                    "archivo_origen": archivo.name
                })

    return pd.DataFrame(resultados)


def main():
    spark = (
        SparkSession.builder
        .appName("Danper_Agroindustria_Silver")
        .master("local[2]")
        .getOrCreate()
    )

    try:
        with TemporaryDirectory() as temporal:
            subprocess.run(
                [
                    "hdfs", "dfs", "-get",
                    f"{BRONZE}/*.xlsx", temporal
                ],
                check=True
            )

            ruta = Path(temporal)

            datos, incidencias, cuadros = (
                extraer_agroindustria(ruta=ruta)
            )

            reporte = validar_totales(
                ruta, datos, incidencias
            )

        print("===== EXTRACCION =====")
        print("Registros:", len(datos))
        print("Cuadros:", len(cuadros))
        print("Valores no numericos:", len(incidencias))

        if len(cuadros) != 18 or datos.empty:
            raise ValueError(
                "La extraccion no tiene la cobertura esperada"
            )

        if reporte.empty:
            raise ValueError(
                "No se pudieron validar los totales anuales"
            )

        # Convertir datos a PySpark.
        df = spark.createDataFrame(datos.to_dict("records"))

        duplicados = (
            df.count()
            - df.select(
                "cultivo", "cuadro_origen",
                "anio", "numero_mes"
            ).distinct().count()
        )

        negativos = df.filter(
            col("cantidad_t") < 0
        ).count()

        nulos = df.filter(
            col("cantidad_t").isNull()
        ).count()

        print("\n===== CALIDAD SILVER =====")
        print("Duplicados:", duplicados)
        print("Negativos:", negativos)
        print("Nulos numericos:", nulos)

        if duplicados or negativos or nulos:
            raise ValueError(
                "Existen incidencias criticas en los datos"
            )

        print("\n===== TOTALES ANUALES =====")
        print(reporte["estado"].value_counts())

        # Guardar observaciones mensuales.
        df.write.mode("overwrite").parquet(SILVER)

        # Guardar incidencias de valores no numericos.
        if not incidencias.empty:
            df_ausentes = spark.createDataFrame(
                incidencias.to_dict("records")
            )
            df_ausentes.write.mode("overwrite").parquet(
                f"{CALIDAD}/valores_no_numericos"
            )

        # Guardar validacion anual.
        df_reporte = spark.createDataFrame(
            reporte.to_dict("records")
        )
        df_reporte.write.mode("overwrite").parquet(
            f"{CALIDAD}/totales_anuales"
        )

        print("\n===== RESULTADO =====")
        print("Silver:", SILVER)
        print("Registros guardados:", df.count())
        print("Reportes de calidad guardados")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
