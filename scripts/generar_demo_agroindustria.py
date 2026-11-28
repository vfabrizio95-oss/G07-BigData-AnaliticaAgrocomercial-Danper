"""Genera Excel SIMULADOS de ingreso a planta para la demostración en vivo.

El modelo de abastecimiento se alimenta del ingreso mensual de materia prima
a las plantas de La Libertad (fuente agroindustria). Para mostrar en la
sustentación que un dato nuevo recorre todo el pipeline y llega al tablero
pasando por el modelo, este script crea uno o dos Excel con el MISMO formato
que los originales (cuadro 7 para alcachofa y cuadro 64 para espárrago), con
unos pocos meses del año siguiente al último dato.

Los valores son simulados: el promedio del mismo mes en los 3 últimos años
válidos, multiplicado por --factor y por una variación propia de cada mes
(entre −25 % y +25 %, siempre la misma para un mismo cultivo y mes), para que
algunos meses caigan dentro de la banda del plan y otros fuera. Cada archivo lo indica en su nombre
("DEMO") y en su primera fila. No son datos reales y deben retirarse después
de la demostración.

Cada archivo lleva en el nombre el año y los meses que simula, por ejemplo
"... ALCACHOFA 2025 DEMO 01-02.xlsx". Con --continuar se generan los N meses
siguientes a la última DEMO que ya exista (--cantidad, 2 por defecto: 01-02, luego 03-04, ...): así la
demostración se puede repetir y cada vez llega un dato nuevo al tablero.

Uso:
    python scripts/generar_demo_agroindustria.py --salida /tmp/demo
    python scripts/generar_demo_agroindustria.py --meses 1 2 --factor 1.3 --salida /tmp/demo
    python scripts/generar_demo_agroindustria.py --continuar --salida /tmp/demo

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
import random
import re

import pandas as pd

import config
from extractor_agroindustria import MESES, extraer_agroindustria

# cultivo -> (cuadro, presentación del ingreso a planta, años faltantes en la fuente)
SERIES = {
    "ALCACHOFA": (7, "PARA PROCESAR", {2017, 2018}),
    "ESPARRAGO": (64, "NATURAL", {2016, 2024}),
}


PATRON_DEMO = re.compile(r"(\d{4}) DEMO(?: (\d{2})-(\d{2}))?\.xlsx$", re.IGNORECASE)


def proximo_bloque(nombres, anio_inicial, cantidad=2):
    """Año y meses (hasta `cantidad`) que siguen a la última DEMO entre `nombres`.

    Sin DEMO previas se empieza en enero de anio_inicial. Un bloque no cruza
    de año: si quedan menos meses en el año, se generan solo los que quedan, y
    el bloque siguiente empieza en enero del año siguiente.
    """
    ultimo = None
    for nombre in nombres:
        m = PATRON_DEMO.search(nombre)
        if m:
            anio, mes = int(m.group(1)), int(m.group(3) or 2)
            ultimo = max(ultimo or (0, 0), (anio, mes))
    if ultimo is None:
        anio, inicio = anio_inicial, 1
    elif ultimo[1] >= 12:
        anio, inicio = ultimo[0] + 1, 1
    else:
        anio, inicio = ultimo[0], ultimo[1] + 1
    return anio, list(range(inicio, min(inicio + cantidad - 1, 12) + 1))


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
    ap.add_argument("--cantidad", type=int, default=2, choices=range(1, 13), metavar="N",
                    help="con --continuar: cuántos meses generar (por defecto 2)")
    ap.add_argument("--continuar", action="store_true",
                    help="generar los 2 meses siguientes a la última DEMO de DANPER_DATASETS/agroindustria")
    args = ap.parse_args()
    for archivo in generar(args.salida, anio=args.anio, meses=args.meses, factor=args.factor,
                           cultivos=args.cultivos, continuar=args.continuar,
                           cantidad=args.cantidad):
        print(archivo)


def generar(salida, anio=None, meses=(1, 2), factor=1.0, cultivos=tuple(SERIES),
            continuar=False, nombres_previos=None, cantidad=2):
    """Escribe los Excel DEMO en `salida` y devuelve sus rutas con un detalle.

    nombres_previos: nombres de archivos DEMO ya cargados (por ejemplo, los del
    bucket S3); si no se indica, se usan los de DANPER_DATASETS/agroindustria.
    """
    datos, _, _ = extraer_agroindustria()  # Excel de DANPER_DATASETS
    datos = datos[~datos["archivo_origen"].str.upper().str.contains("DEMO")]
    anio_real = int(datos["anio"].max()) + 1
    if continuar:
        if nombres_previos is None:
            carpeta = config.DATASETS / "agroindustria"
            nombres_previos = [p.name for p in carpeta.glob("*DEMO*")] if carpeta.is_dir() else []
        anio, meses = proximo_bloque(nombres_previos, anio_real, cantidad)
    anio = anio or anio_real
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    resultado = []

    for cultivo in cultivos:
        cuadro, presentacion, faltantes = SERIES[cultivo]
        valores = {m: round(promedio_3a(datos, cultivo, cuadro, faltantes, anio, m) * factor
                            * random.Random(f"{cultivo}-{anio}-{m}").uniform(0.75, 1.25), 3)
                   for m in meses}
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
        sufijo = f"{min(meses):02d}-{max(meses):02d}"
        archivo = salida / f"LA LIBERTAD AGROINDUSTRIA DE {cultivo} {anio} DEMO {sufijo}.xlsx"
        hoja.to_excel(archivo, sheet_name=cultivo, header=False, index=False)
        detalle = ", ".join(f"{MESES[m - 1]} {v:,.0f} t" for m, v in valores.items())
        resultado.append(f"{archivo}: {detalle}")
    return resultado


if __name__ == "__main__":
    main()
