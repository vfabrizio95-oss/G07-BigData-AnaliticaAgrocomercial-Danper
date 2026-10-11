
import argparse
import re
import subprocess
import tempfile
import time
from pathlib import Path

from pyspark.sql import SparkSession


BRONZE = "/danper/bronze/sostenibilidad/danper"
SILVER = "/danper/silver/sostenibilidad/danper_indicadores"

REPORTES = {
    2022: "Reporte-de-Sostenibilidad-Danper-2022_Sello-GRI.pdf",
    2023: "Reporte-de-sostenibilidad-DANPER-2023_VF_Final-2.pdf",
    2024: "20102025-Reporte-de-Sostenibilidad-Danper-2024-web-1.pdf",
}

# Indicadores identificados y contrastados con las páginas
# de los reportes. No son cálculos estimados por el script.
# Formato:
# (anio_indicador, anio_reporte, pagina_pdf,
#  indicador, valor, unidad, alcance, evidencia_textual)

DATOS = [
    (2022, 2022, 71, "energia_renovable_porcentaje",
     0.34, "%", "Consumo total de energia Danper", "0.34%"),

    (2022, 2023, 88, "emisiones_gei_alcance_1",
     12040.40, "t CO2eq", "Alcance 1", "12,040.40"),

    (2022, 2023, 88, "emisiones_gei_alcance_2",
     5569.96, "t CO2eq", "Alcance 2", "5,569.96"),

    (2022, 2023, 88, "emisiones_gei_alcance_3",
     15108.40, "t CO2eq", "Alcance 3", "15,108.40"),

    (2023, 2023, 86, "remocion_carbono_compositan",
     7694.7, "t CO2eq", "Fundo Compositan", "7,694.7"),

    (2023, 2023, 86, "valorizacion_residuos_porcentaje",
     77.0, "%", "Residuos solidos Danper", "77%"),

    (2023, 2023, 86, "residuos_valorizados",
     26626.25, "toneladas", "Residuos solidos Danper",
     "26,626.25"),

    (2023, 2024, 112, "consumo_total_energia",
     141252.0, "GJ", "Entidades bajo control de Danper",
     "141,252"),

    (2024, 2024, 115, "remocion_carbono_compositan",
     8061.6, "t CO2eq", "Fundo Compositan", "8,061.6"),

    (2024, 2024, 115, "valorizacion_residuos_porcentaje",
     99.1, "%", "Residuos solidos Danper", "99.1"),

    (2024, 2024, 115, "residuos_valorizados",
     48597.32, "toneladas", "Residuos solidos Danper",
     "48 597.32"),

    (2024, 2024, 112, "consumo_total_energia",
     141101.0, "GJ", "Entidades bajo control de Danper",
     "141,101"),
]


def comando(args):
    return subprocess.run(
        args, capture_output=True, text=True, check=True,
        timeout=120
    )


def normalizar_espacios(texto):
    return re.sub(r"\s+", " ", texto).strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ejecutar", action="store_true")
    args = parser.parse_args()

    inicio = time.time()

    print("===== SOSTENIBILIDAD DANPER SILVER =====", flush=True)
    print("MODO:", "ESCRITURA" if args.ejecutar
          else "SOLO VALIDACION", flush=True)

    if args.ejecutar:
        prueba = subprocess.run(
            ["hdfs", "dfs", "-test", "-e", SILVER],
            capture_output=True
        )
        if prueba.returncode == 0:
            raise RuntimeError(
                "El destino ya existe. No se sobrescribira: "
                + SILVER
            )
        if prueba.returncode != 1:
            raise RuntimeError(
                "No se pudo verificar el destino en HDFS"
            )

    filas = []

    with tempfile.TemporaryDirectory() as carpeta:
        carpeta = Path(carpeta)

        for indice, (anio, nombre) in enumerate(
            REPORTES.items(), 1
        ):
            print(
                f"\n[{indice}/3] REPORTE {anio}",
                flush=True
            )

            origen = f"{BRONZE}/{nombre}"
            local = carpeta / nombre

            comando(["hdfs", "dfs", "-get", origen, str(local)])

            indicadores = [
                d for d in DATOS if d[1] == anio
            ]

            for dato in indicadores:
                (anio_ind, anio_rep, pagina, indicador,
                 valor, unidad, alcance, evidencia) = dato

                resultado = comando([
                    "pdftotext",
                    "-f", str(pagina),
                    "-l", str(pagina),
                    "-layout", str(local), "-"
                ])

                texto = normalizar_espacios(resultado.stdout)

                if normalizar_espacios(evidencia) not in texto:
                    raise ValueError(
                        f"Evidencia no localizada: "
                        f"{anio_rep}, pagina {pagina}, "
                        f"{indicador}, {evidencia}"
                    )

                filas.append({
                    "anio_indicador": anio_ind,
                    "anio_reporte": anio_rep,
                    "pagina_pdf": pagina,
                    "indicador": indicador,
                    "valor": float(valor),
                    "unidad": unidad,
                    "alcance": alcance,
                    "archivo_origen": nombre,
                    "ruta_bronze": origen,
                    "evidencia_textual": evidencia,
                    "metodo_extraccion": "transcripcion_validada_pdf"
                })

                print(
                    f"  OK | {indicador}: {valor} {unidad}",
                    flush=True
                )

            print(
                f"PROGRESO EXTRACCION: "
                f"{indice / 3 * 100:.0f}%",
                flush=True
            )

    claves = [
        (f["anio_indicador"], f["indicador"], f["alcance"])
        for f in filas
    ]

    if len(claves) != len(set(claves)):
        raise ValueError("Indicadores duplicados")

    if len(filas) != 12:
        raise ValueError("Cantidad de indicadores inesperada")

    print("\n===== VERIFICACION SPARK =====", flush=True)

    spark = (
        SparkSession.builder
        .appName("Danper_Sostenibilidad_Silver")
        .master("local[2]")
        .getOrCreate()
    )

    try:
        spark.sparkContext.setLogLevel("ERROR")

        columnas = [
            "anio_indicador", "anio_reporte", "pagina_pdf",
            "indicador", "valor", "unidad", "alcance",
            "archivo_origen", "ruta_bronze",
            "evidencia_textual", "metodo_extraccion"
        ]

        registros = [
            tuple(f[c] for c in columnas)
            for f in filas
        ]

        df = spark.createDataFrame(registros, columnas)

        df.groupBy("anio_indicador").count().orderBy(
            "anio_indicador"
        ).show()

        print("TOTAL INDICADORES:", df.count(), flush=True)

        if args.ejecutar:
            df.write.mode("errorifexists").parquet(SILVER)
            confirmados = spark.read.parquet(SILVER).count()
            print("REGISTROS ESCRITOS:", confirmados, flush=True)

            if confirmados != 12:
                raise ValueError("Conteo de salida incorrecto")
        else:
            print(
                "VALIDACION COMPLETADA: NO SE ESCRIBIO EN SILVER",
                flush=True
            )

    finally:
        spark.stop()

    print(
        "TIEMPO TOTAL:",
        round(time.time() - inicio, 2),
        "segundos",
        flush=True
    )


if __name__ == "__main__":
    main()
