"""Tabla de control del pipeline Danper.

Registra cada archivo cargado en Bronze y en qué capas ya fue procesado.
Se guarda como CSV en HDFS ({DANPER_HDFS_BASE}/control/archivos.csv) para no
depender de la base de datos; cada etapa la usa para procesar solo lo pendiente.

Columnas:
    ruta_bronze   ruta del archivo en HDFS (clave)
    ruta_local    ruta relativa a la carpeta de datasets
    fuente        fuente Silver que lo procesa (ver fuente_de)
    sha256        huella del contenido
    tamano_bytes  tamaño del archivo
    fecha_carga   fecha y hora de carga en Bronze
    silver_ok     fecha y hora en que su fuente se procesó en Silver
    gold_ok       fecha y hora en que Gold se recalculó con él
    postgres_ok   fecha y hora en que Gold se publicó en PostgreSQL

Uso:
    python scripts/control.py               # resumen
    python scripts/control.py --pendientes  # archivos pendientes por capa
    python scripts/control.py --inicializar # registrar la carga actual de Bronze
"""
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import argparse
import csv
import io
import subprocess

import config

CONTROL = f"{config.HDFS_BASE}/control"
ARCHIVO_CONTROL = f"{CONTROL}/archivos.csv"
INVENTARIO_LOCAL = Path(__file__).resolve().parent.parent / "reportes" / "inventario_bronze.csv"

COLUMNAS = [
    "ruta_bronze", "ruta_local", "fuente", "sha256", "tamano_bytes",
    "fecha_carga", "silver_ok", "gold_ok", "postgres_ok",
]
CAPAS = ("silver_ok", "gold_ok", "postgres_ok")

# Fuentes que no tienen transformación Silver (se guardan solo en Bronze).
SIN_SILVER = "sin_silver"


def ahora():
    return datetime.now().isoformat(timespec="seconds")


def fuente_de(ruta_bronze):
    """Fuente Silver que procesa un archivo de Bronze."""
    relativo = ruta_bronze[len(config.BRONZE) + 1:]
    partes = relativo.split("/")

    if partes[0] == "abastecimiento":
        if len(partes) > 1 and partes[1] == "mercado_productores":
            return "mercado_productores"
        return "abastecimiento"
    if partes[0] == "exportaciones":
        if len(partes) > 1 and partes[1] == "danper":
            return "exportaciones_danper"
        return "exportaciones_regionales" if len(partes) == 2 else SIN_SILVER
    if partes[0] == "costos":
        if len(partes) > 1 and partes[1] == "ena_2025":
            return "ena_2025"
        return "costos" if len(partes) == 2 else SIN_SILVER
    if partes[0] in ("produccion", "agroindustria", "sostenibilidad"):
        return partes[0]
    return SIN_SILVER


def _hdfs(*argumentos, check=True):
    return subprocess.run(
        ["hdfs", "dfs", *argumentos],
        capture_output=True, text=True, check=check,
    )


def existe():
    return _hdfs("-test", "-e", ARCHIVO_CONTROL, check=False).returncode == 0


def leer():
    """Devuelve {ruta_bronze: fila}. Vacío si la tabla aún no existe."""
    if not existe():
        return {}
    contenido = _hdfs("-cat", ARCHIVO_CONTROL).stdout
    filas = csv.DictReader(io.StringIO(contenido))
    return {fila["ruta_bronze"]: {c: fila.get(c, "") for c in COLUMNAS} for fila in filas}


def guardar(registros):
    """Escribe la tabla completa en HDFS (put -f es atómico: copia y renombra)."""
    with TemporaryDirectory() as temporal:
        local = Path(temporal) / "archivos.csv"
        with local.open("w", newline="", encoding="utf-8") as f:
            escritor = csv.DictWriter(f, fieldnames=COLUMNAS)
            escritor.writeheader()
            for ruta in sorted(registros):
                escritor.writerow(registros[ruta])
        _hdfs("-mkdir", "-p", CONTROL)
        _hdfs("-put", "-f", str(local), ARCHIVO_CONTROL)


def nuevo_registro(ruta_bronze, ruta_local, sha256, tamano, procesado=""):
    return {
        "ruta_bronze": ruta_bronze,
        "ruta_local": ruta_local,
        "fuente": fuente_de(ruta_bronze),
        "sha256": sha256,
        "tamano_bytes": str(tamano),
        "fecha_carga": ahora(),
        "silver_ok": procesado,
        "gold_ok": procesado,
        "postgres_ok": "",
    }


def pendientes(registros, capa):
    """Registros que aún no pasaron por la capa indicada."""
    return [
        r for r in registros.values()
        if not r[capa] and (capa != "silver_ok" or r["fuente"] != SIN_SILVER)
    ]


def marcar(registros, filas, capa):
    momento = ahora()
    for fila in filas:
        registros[fila["ruta_bronze"]][capa] = momento


def inicializar():
    """Registra los archivos que ya están en Bronze como carga base procesada.

    Usa el SHA-256 de reportes/inventario_bronze.csv (verificado al subirlos)
    y comprueba que cada archivo exista en HDFS con el mismo tamaño.
    """
    if existe():
        raise RuntimeError(f"La tabla de control ya existe: {ARCHIVO_CONTROL}")

    import ingesta_bronze

    with INVENTARIO_LOCAL.open(encoding="utf-8") as f:
        inventario = {fila["ruta_relativa"]: fila for fila in csv.DictReader(f)}

    destinos = ingesta_bronze.preparar_inventario()
    en_hdfs = ingesta_bronze.obtener_archivos_hdfs()
    registros = {}

    for destino, archivo in destinos.items():
        relativo = archivo.relative_to(config.DATASETS).as_posix()
        if relativo not in inventario:
            raise ValueError(f"Archivo local fuera del inventario: {relativo}")
        if en_hdfs.get(destino) != archivo.stat().st_size:
            raise ValueError(f"No está en Bronze con el mismo tamaño: {destino}")
        registros[destino] = nuevo_registro(
            destino, relativo, inventario[relativo]["sha256"],
            archivo.stat().st_size, procesado="carga_base",
        )

    guardar(registros)
    print(f"Tabla de control creada: {ARCHIVO_CONTROL} ({len(registros)} archivos)")


def resumen(registros, detalle=False):
    from collections import Counter

    print(f"Tabla de control: {ARCHIVO_CONTROL}")
    print("Archivos registrados:", len(registros))
    por_fuente = Counter(r["fuente"] for r in registros.values())
    for fuente, cantidad in sorted(por_fuente.items()):
        print(f"  {fuente:26s} {cantidad:4d}")
    for capa in CAPAS:
        lista = pendientes(registros, capa)
        print(f"Pendientes {capa.replace('_ok', ''):9s}: {len(lista)}")
        if detalle:
            for r in lista:
                print("   ", r["ruta_bronze"])


def main():
    ap = argparse.ArgumentParser(description="Tabla de control del pipeline Danper")
    ap.add_argument("--inicializar", action="store_true",
                    help="Registrar la carga actual de Bronze como procesada")
    ap.add_argument("--pendientes", action="store_true",
                    help="Listar los archivos pendientes por capa")
    args = ap.parse_args()

    if args.inicializar:
        inicializar()
    resumen(leer(), detalle=args.pendientes)


if __name__ == "__main__":
    main()
