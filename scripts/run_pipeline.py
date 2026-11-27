"""Orquestador del pipeline Danper: Bronze -> Silver -> Gold -> Modelo -> PostgreSQL.

Cada etapa procesa solo lo pendiente según la tabla de control
(/danper/control/archivos.csv):

1. Bronze: sube a HDFS los archivos nuevos de la carpeta de datasets.
2. Silver: por cada fuente con archivos nuevos.
     - abastecimiento (PDF GMML): incremental, solo los PDF nuevos.
     - otras fuentes: se vuelve a ejecutar su transformación (son pequeñas).
     - ENA 2025 y sostenibilidad: fuentes cerradas; un archivo nuevo se informa
       y requiere reproceso manual.
3. Gold: --rebuild (recalcula desde Silver y reemplaza sin perder lo anterior).
4. Modelo: aplica el PipelineModel ya entrenado y guardado en HDFS a los datos
   actuales de Gold (modelo_abastecimiento.py --aplicar). No reentrena: el
   entrenamiento se hace aparte, una vez, con modelo_abastecimiento.py.
5. PostgreSQL: publica Gold (incluidas las tablas del modelo) para el dashboard.

Uso:
    python scripts/run_pipeline.py               # una pasada
    python scripts/run_pipeline.py --vigilar     # revisar cada 60 s
    python scripts/run_pipeline.py --vigilar 30  # revisar cada 30 s
    python scripts/run_pipeline.py --sin-postgres
"""
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import argparse
import subprocess
import sys
import time

import config
import control

SCRIPTS = Path(__file__).resolve().parent

# Fuente -> comando que la reconstruye completa en Silver.
SILVER_COMPLETO = {
    "produccion": ["transformacion_silver.py", "--ejecutar"],
    "exportaciones_danper": ["transformacion_exportaciones_danper_silver.py", "--ejecutar"],
    "exportaciones_regionales": ["transformacion_exportaciones_regionales_silver.py"],
    "agroindustria": ["transformacion_agroindustria_silver.py"],
    "costos": ["transformacion_costos_silver.py"],
    "mercado_productores": ["transformacion_mercado_productores_silver.py", "--ejecutar"],
}
SILVER_INCREMENTAL = {
    "abastecimiento": ["transformacion_abastecimiento_silver.py", "--ejecutar", "--archivos"],
}
SILVER_MANUAL = {"ena_2025", "sostenibilidad"}


class ErrorEtapa(RuntimeError):
    pass


def log(mensaje):
    print(f"[{datetime.now():%H:%M:%S}] {mensaje}", flush=True)


def ejecutar(etapa, comando):
    inicio = time.time()
    log(f"{etapa}: iniciando")
    proceso = subprocess.run(comando, cwd=SCRIPTS, capture_output=True, text=True)
    duracion = time.time() - inicio
    if proceso.returncode != 0:
        print(proceso.stdout[-3000:], proceso.stderr[-3000:], sep="\n")
        raise ErrorEtapa(f"{etapa} falló (código {proceso.returncode}) tras {duracion:.1f} s")
    log(f"{etapa}: OK en {duracion:.1f} s")
    return duracion


def python(script, *args):
    return [sys.executable, str(SCRIPTS / script), *args]


def spark_submit(script, *args):
    return ["spark-submit", str(SCRIPTS / script), *args]


def etapa_silver(registros):
    pendientes = defaultdict(list)
    for fila in control.pendientes(registros, "silver_ok"):
        pendientes[fila["fuente"]].append(fila)

    if not pendientes:
        log("Silver: sin archivos pendientes")
        return 0.0

    total = 0.0
    for fuente, filas in sorted(pendientes.items()):
        if fuente in SILVER_MANUAL:
            log(f"Silver: AVISO {len(filas)} archivo(s) nuevo(s) de {fuente}: "
                "fuente cerrada, requiere reproceso manual (se omite)")
            continue
        if fuente in SILVER_INCREMENTAL:
            script, *args = SILVER_INCREMENTAL[fuente]
            comando = python(script, *args, *(f["ruta_bronze"] for f in filas))
        elif fuente in SILVER_COMPLETO:
            comando = python(*SILVER_COMPLETO[fuente])
        else:
            raise ErrorEtapa(f"Fuente sin transformación Silver definida: {fuente}")

        total += ejecutar(f"Silver {fuente} ({len(filas)} archivo/s)", comando)
        control.marcar(registros, filas, "silver_ok")
        control.guardar(registros)
    return total


def una_pasada(con_postgres=True):
    inicio = time.time()
    log("===== PIPELINE DANPER =====")
    tiempos = {}

    tiempos["bronze"] = ejecutar("Bronze", python("ingesta_bronze.py", "--ejecutar"))
    registros = control.leer()

    tiempos["silver"] = etapa_silver(registros)

    gold_pendientes = [r for r in registros.values() if r["silver_ok"] and not r["gold_ok"]]
    if gold_pendientes:
        tiempos["gold"] = ejecutar("Gold", spark_submit("procesamiento_gold.py", "--rebuild"))
        tiempos["modelo"] = ejecutar("Modelo (aplicar)",
                                     spark_submit("modelo_abastecimiento.py", "--aplicar"))
        control.marcar(registros, gold_pendientes, "gold_ok")
        control.guardar(registros)
    else:
        log("Gold: sin cambios en Silver")

    if con_postgres:
        pg_pendientes = [r for r in registros.values() if r["gold_ok"] and not r["postgres_ok"]]
        if pg_pendientes:
            tiempos["postgres"] = ejecutar("PostgreSQL", python("publicar_postgres.py"))
            control.marcar(registros, pg_pendientes, "postgres_ok")
            control.guardar(registros)
        else:
            log("PostgreSQL: sin cambios en Gold")

    resumen = ", ".join(f"{k} {v:.1f} s" for k, v in tiempos.items())
    log(f"===== FIN: {time.time() - inicio:.1f} s ({resumen}) =====")


def archivos_locales():
    return {
        p.relative_to(config.DATASETS).as_posix()
        for p in config.DATASETS.rglob("*") if p.is_file()
    }


def vigilar(intervalo, con_postgres):
    log(f"Vigilando {config.DATASETS} cada {intervalo} s (Ctrl+C para salir)")
    capas = ("silver_ok", "gold_ok", "postgres_ok") if con_postgres else ("silver_ok", "gold_ok")

    def estado():
        registros = control.leer()
        conocidos = {r["ruta_local"] for r in registros.values()}
        pendientes = any(
            r for capa in capas for r in control.pendientes(registros, capa)
            if r["fuente"] not in SILVER_MANUAL
        )
        return conocidos, pendientes

    conocidos, hay_pendientes = estado()

    while True:
        nuevos = sorted(archivos_locales() - conocidos)
        if nuevos or hay_pendientes:
            for ruta in nuevos:
                log(f"Archivo nuevo detectado: {ruta}")
            if nuevos:
                time.sleep(2)  # dar tiempo a que termine de copiarse
            try:
                una_pasada(con_postgres)
            except ErrorEtapa as error:
                log(f"ERROR: {error}. Se reintentará en la próxima revisión.")
            conocidos, hay_pendientes = estado()
        time.sleep(intervalo)


def main():
    ap = argparse.ArgumentParser(description="Orquestador del pipeline Danper")
    ap.add_argument("--vigilar", nargs="?", const=60, type=int, metavar="SEGUNDOS",
                    help="Revisar la carpeta de datasets cada N segundos (60 por defecto)")
    ap.add_argument("--sin-postgres", action="store_true",
                    help="No publicar en PostgreSQL")
    args = ap.parse_args()

    try:
        if args.vigilar:
            vigilar(args.vigilar, not args.sin_postgres)
        else:
            una_pasada(not args.sin_postgres)
    except ErrorEtapa as error:
        log(f"ERROR: {error}")
        sys.exit(1)
    except KeyboardInterrupt:
        log("Vigilancia detenida")


if __name__ == "__main__":
    main()
