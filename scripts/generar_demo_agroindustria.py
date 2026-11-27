"""Genera Excel SIMULADOS de ingreso a planta para la demostración en vivo.

El modelo de abastecimiento se alimenta del ingreso mensual de materia prima
a las plantas de La Libertad (fuente agroindustria). Para mostrar en la
sustentación que un dato nuevo recorre todo el pipeline y llega al tablero
pasando por el modelo, este script crea uno o dos Excel con el MISMO formato
que los originales (cuadro 7 para alcachofa y cuadro 64 para espárrago), con
unos pocos meses del año siguiente al último dato.

Los valores son simulados: el promedio del mismo mes en los 3 últimos años
válidos, multiplicado por --factor. Cada archivo lo indica en su nombre
("DEMO") y en su primera fila. No son datos reales y deben retirarse después
de la demostración.

Uso:
    python scripts/generar_demo_agroindustria.py --salida /tmp/demo
    python scripts/generar_demo_agroindustria.py --meses 1 2 --factor 1.3 --salida /tmp/demo

Luego se sube a s3://<bucket>/datasets/agroindustria/ (en AWS) o se copia a
DANPER_DATASETS/agroindustria/ (en local), y el pipeline lo procesa solo.

Cómo retirarlo después de la demostración (en el master, como danper):
    1. Borrar el archivo DEMO de S3 (consola) y de $DANPER_DATASETS/agroindustria/.
    2. hdfs dfs -rm "/danper/bronze/agroindustria/*DEMO*"
    3. Quitar su fila de la tabla de control:
         hdfs dfs -cat /danper/control/archivos.csv | grep -v DEMO > /tmp/archivos.csv
         hdfs dfs -put -f /tmp/archivos.csv /danper/control/archivos.csv
    4. Reprocesar sin el archivo:
         python scripts/transformacion_agroindustria_silver.py
         spark-submit scripts/procesamiento_gold.py --rebuild
         spark-submit scripts/modelo_abastecimiento.py --aplicar
         python scripts/publicar_postgres.py
"""
from pathlib import Path
import argparse

import pandas as pd

from extractor_agroindustria import MESES, extraer_agroindustria

# cultivo -> (cuadro, presentación del ingreso a planta, años faltantes en la fuente)
SERIES = {
    "ALCACHOFA": (7, "PARA PROCESAR", {2017, 2018}),
    "ESPARRAGO": (64, "NATURAL", {2016, 2024}),
}


def promedio_3a(datos, cultivo, cuadro, faltantes, anio, mes):
    serie = datos[(datos["cultivo"] == cultivo) & (datos["cuadro_origen"] == cuadro)
                  & (datos["numero_mes"] == mes) & (datos["anio"] < anio)
                  & ~datos["anio"].isin(faltantes)]
    return serie.sort_values("anio").tail(3)["cantidad_t"].mean()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--salida", type=Path, required=True, help="carpeta donde se escriben los Excel")
    ap.add_argument("--anio", type=int, help="año simulado (por defecto, el siguiente al último dato)")
    ap.add_argument("--meses", type=int, nargs="+", default=[1, 2], help="meses simulados (1-12)")
    ap.add_argument("--factor", type=float, default=1.0,
                    help="multiplica el promedio de 3 años (por ejemplo 1.3 = 30 %% más)")
    ap.add_argument("--cultivos", nargs="+", default=list(SERIES), choices=list(SERIES))
    args = ap.parse_args()

    datos, _, _ = extraer_agroindustria()  # Excel originales de DANPER_DATASETS
    datos = datos[~datos["archivo_origen"].str.upper().str.contains("DEMO")]
    anio = args.anio or int(datos["anio"].max()) + 1
    args.salida.mkdir(parents=True, exist_ok=True)

    for cultivo in args.cultivos:
        cuadro, presentacion, faltantes = SERIES[cultivo]
        valores = {m: round(promedio_3a(datos, cultivo, cuadro, faltantes, anio, m) * args.factor, 3)
                   for m in args.meses}
        fila = [anio, round(sum(valores.values()), 3)]
        fila += [valores.get(m) for m in range(1, 13)]
        hoja = pd.DataFrame([
            [f"{cultivo} {presentacion} (DATOS SIMULADOS PARA DEMOSTRACION)"] + [None] * 13,
            [None] * 14,
            [f"CUADRO N° {cuadro:03d} LA LIBERTAD: INGRESO DE {cultivo} A PLANTA (DEMO)"] + [None] * 13,
            ["(t)"] + [None] * 13,
            ["AÑO", "TOTAL", *MESES],
            fila,
            ["FUENTE: SIMULADO A PARTIR DEL PROMEDIO DE LOS 3 ULTIMOS AÑOS VALIDOS"] + [None] * 13,
        ])
        archivo = args.salida / f"LA LIBERTAD AGROINDUSTRIA DE {cultivo} {anio} DEMO.xlsx"
        hoja.to_excel(archivo, sheet_name=cultivo, header=False, index=False)
        detalle = ", ".join(f"{MESES[m - 1]} {v:,.0f} t" for m, v in valores.items())
        print(f"{archivo}: {detalle}")


if __name__ == "__main__":
    main()
