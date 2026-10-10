from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess

import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql.functions import col

from extractor_exportaciones_regionales import (
    extraer_exportaciones_regionales,
    identificar_cultivo,
    convertir_numero,
    CONFIGURACION,
)

BRONZE = "/danper/bronze/exportaciones"
SILVER = "/danper/silver/exportaciones/regionales"
CALIDAD = "/danper/calidad/exportaciones/regionales"


def validar_totales(ruta, datos, incidencias):
    resultados = []

    for archivo in sorted(ruta.glob("*.xlsx")):
        cultivo = identificar_cultivo(archivo.name)

        if cultivo is None:
            continue

        libro = pd.ExcelFile(archivo)

        for hoja in libro.sheet_names:
            tabla = pd.read_excel(
                archivo, sheet_name=hoja, header=None
            )

            encabezados = []

            for i in range(len(tabla)):
                fila = [
                    str(v).strip().upper()
                    if pd.notna(v) else ""
                    for v in tabla.iloc[i].tolist()
                ]

                for j, valor in enumerate(fila):
                    if (
                        valor in ("AÑO", "ANO")
                        and j + 2 < len(fila)
                        and fila[j + 1].startswith("ENE")
                        and fila[j + 2].startswith("FEB")
                    ):
                        encabezados.append((i, j))
                        break

            for indice, (inicio, col_anio) in enumerate(
                encabezados
            ):
                indicador = CONFIGURACION[cultivo][indice]

                # El precio FOB es una razon: no se suma.
                if indicador == "PRECIO_FOB":
                    continue

                fin = (
                    encabezados[indice + 1][0]
                    if indice + 1 < len(encabezados)
                    else len(tabla)
                )

                for i in range(inicio + 1, fin):
                    anio_valor = convertir_numero(
                        tabla.iloc[i, col_anio]
                    )

                    if (
                        anio_valor is None
                        or not anio_valor.is_integer()
                        or not 2012 <= anio_valor <= 2023
                    ):
                        continue

                    anio = int(anio_valor)
                    total = convertir_numero(
                        tabla.iloc[i, col_anio + 13]
                    )

                    seleccion = datos[
                        (datos["cultivo"] == cultivo)
                        & (datos["indicador"] == indicador)
                        & (datos["anio"] == anio)
                    ]

                    ausentes = incidencias[
                        (incidencias["cultivo"] == cultivo)
                        & (incidencias["indicador"] == indicador)
                        & (incidencias["anio"] == anio)
                    ]

                    suma = float(seleccion["valor"].sum())
                    faltantes = len(ausentes)

                    if total is None:
                        estado = "TOTAL_AUSENTE"
                        diferencia = None
                    else:
                        diferencia = abs(float(total) - suma)

                        if faltantes:
                            estado = "INCOMPLETO"
                        elif diferencia > 0.01:
                            estado = "DIFERENCIA"
                        else:
                            estado = "VALIDADO"

                    resultados.append({
                        "cultivo": cultivo,
                        "indicador": indicador,
                        "anio": anio,
                        "total_anual": (
                            float(total)
                            if total is not None else None
                        ),
                        "suma_mensual": suma,
                        "diferencia": diferencia,
                        "meses_ausentes": faltantes,
                        "estado": estado,
                        "archivo_origen": archivo.name,
                    })

    return pd.DataFrame(resultados)


def main():
    spark = (
        SparkSession.builder
        .appName("Danper_Exportaciones_Regionales_Silver")
        .master("local[2]")
        .getOrCreate()
    )

    try:
        with TemporaryDirectory() as temporal:
            # Leer los originales desde HDFS Bronze.
            subprocess.run(
                [
                    "hdfs", "dfs", "-get",
                    f"{BRONZE}/*.xlsx",
                    temporal
                ],
                check=True
            )

            ruta = Path(temporal)

            datos, incidencias, bloques = (
                extraer_exportaciones_regionales(ruta)
            )

            reporte = validar_totales(
                ruta, datos, incidencias
            )

        print("\n===== EXTRACCION REGIONAL =====")
        print("Registros:", len(datos))
        print("Ausentes:", len(incidencias))
        print("Bloques:", len(bloques))
        print("Totales revisados:", len(reporte))

        if (
            len(datos) != 2043
            or len(incidencias) != 117
            or len(bloques) != 15
            or len(reporte) != 120
        ):
            raise ValueError(
                "Los resultados difieren de la "
                "extraccion local validada"
            )

        df = spark.createDataFrame(
            datos.to_dict("records")
        )

        clave = [
            "cultivo", "indicador",
            "anio", "numero_mes"
        ]

        duplicados = (
            df.count()
            - df.select(*clave).distinct().count()
        )

        negativos = df.filter(
            col("valor") < 0
        ).count()

        nulos = df.filter(
            col("valor").isNull()
        ).count()

        print("\n===== CALIDAD SILVER =====")
        print("Duplicados:", duplicados)
        print("Negativos:", negativos)
        print("Nulos:", nulos)

        if duplicados or negativos or nulos:
            raise ValueError(
                "Se detectaron problemas criticos"
            )

        print("\n===== TOTALES ANUALES =====")
        print(reporte["estado"].value_counts())

        # Almacenar registros mensuales.
        df.write.mode("overwrite").parquet(SILVER)

        # Almacenar ausencias.
        df_ausentes = spark.createDataFrame(
            incidencias.to_dict("records")
        )

        df_ausentes.write.mode("overwrite").parquet(
            f"{CALIDAD}/valores_ausentes"
        )

        # Almacenar verificaciones de totales.
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
