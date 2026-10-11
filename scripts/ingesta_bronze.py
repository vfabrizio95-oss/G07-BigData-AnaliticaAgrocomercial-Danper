
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import subprocess

# ==========================================
# CONFIGURACION DEL PROYECTO
# ==========================================

BASE = Path.home() / "proyecto_danper/datasets"
BRONZE = "/danper/bronze"


# ==========================================
# EJECUCION DE COMANDOS HDFS
# ==========================================

def ejecutar(comando):
    resultado = subprocess.run(
        comando,
        capture_output=True,
        text=True,
        check=True
    )
    return resultado.stdout.strip()


# ==========================================
# INVENTARIO HDFS - UNA SOLA CONSULTA
# ==========================================

def obtener_archivos_hdfs():
    print("Consultando inventario de HDFS...", flush=True)

    salida = ejecutar([
        "hdfs", "dfs", "-ls", "-R", BRONZE
    ])

    archivos = {}

    for linea in salida.splitlines():
        partes = linea.split(maxsplit=7)

        if len(partes) != 8:
            continue

        # Ignorar directorios
        if not partes[0].startswith("-"):
            continue

        tamano = int(partes[4])
        ruta = partes[7]

        archivos[ruta] = tamano

    print(
        "Archivos encontrados en HDFS:",
        len(archivos),
        flush=True
    )

    return archivos


# ==========================================
# CALCULO DE SHA-256
# ==========================================

def sha256_local(archivo):
    resultado = hashlib.sha256()

    with archivo.open("rb") as f:
        while True:
            bloque = f.read(1024 * 1024)

            if not bloque:
                break

            resultado.update(bloque)

    return resultado.hexdigest()


def sha256_hdfs(ruta):
    resultado = hashlib.sha256()

    proceso = subprocess.Popen(
        ["hdfs", "dfs", "-cat", ruta],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    while True:
        bloque = proceso.stdout.read(1024 * 1024)

        if not bloque:
            break

        resultado.update(bloque)

    errores = proceso.stderr.read().decode(
        "utf-8",
        errors="replace"
    )

    codigo = proceso.wait()

    if codigo != 0:
        raise RuntimeError(
            f"Error al leer HDFS: {ruta}\n{errores}"
        )

    return resultado.hexdigest()


# ==========================================
# ASIGNACION DE RUTAS BRONZE
# ==========================================

def obtener_destino(archivo):
    relativo = archivo.relative_to(BASE)
    partes = relativo.parts

    categoria = partes[0]
    nombre = archivo.name

    # Produccion agricola:
    # Mantener compatibilidad con Silver.
    if categoria == "produccion":
        return f"{BRONZE}/produccion/{nombre}"

    # Agroindustria:
    # Mantener compatibilidad con Silver.
    if categoria == "agroindustria":
        return f"{BRONZE}/agroindustria/{nombre}"

    # Exportaciones:
    # Separar Danper, regionales y MINCETUR.
    if categoria == "exportaciones":

        if nombre.startswith("SUNAT_DANPER_"):
            return (
                f"{BRONZE}/exportaciones/"
                f"danper/{nombre}"
            )

        if "mincetur" in partes:
            return (
                f"{BRONZE}/comercio_regional/"
                f"mincetur/{nombre}"
            )

        return f"{BRONZE}/exportaciones/{nombre}"

    # Costos complementarios:
    # Preservar la ruta usada por Silver.
    if categoria == "costos":

        if "complementarios" in partes:
            return f"{BRONZE}/costos/{nombre}"

        # ENA mantiene sus subcarpetas.
        return (
            f"{BRONZE}/costos/"
            + relativo.relative_to("costos").as_posix()
        )

    # Abastecimiento:
    # Preservar los dos PDF originales
    # utilizados por Silver.
    if categoria == "abastecimiento":

        es_gmml = (
            "gran-mercado-mayorista-de-lima"
            in nombre.lower()
        )

        es_pdf_original = nombre.endswith((
            "31-01-2025.pdf",
            "31-12-2025.pdf"
        ))

        if es_gmml and es_pdf_original:
            return (
                f"{BRONZE}/abastecimiento/{nombre}"
            )

        # Nuevos reportes por mercado y ano.
        return (
            f"{BRONZE}/abastecimiento/"
            + relativo.relative_to(
                "abastecimiento"
            ).as_posix()
        )

    # Sostenibilidad, pecuaria y otras fuentes.
    return f"{BRONZE}/{relativo.as_posix()}"


# ==========================================
# PREPARACION DEL INVENTARIO LOCAL
# ==========================================

def preparar_inventario():
    if not BASE.is_dir():
        raise FileNotFoundError(
            f"No existe la carpeta: {BASE}"
        )

    archivos = sorted(
        archivo
        for archivo in BASE.rglob("*")
        if archivo.is_file()
    )

    if not archivos:
        raise ValueError(
            "No se encontraron datasets locales."
        )

    destinos = {}

    for archivo in archivos:
        destino = obtener_destino(archivo)

        if destino in destinos:
            raise ValueError(
                "Dos archivos tienen el mismo destino HDFS:\n"
                f"{destinos[destino]}\n"
                f"{archivo}\n"
                f"Destino: {destino}"
            )

        destinos[destino] = archivo

    return destinos


# ==========================================
# SIMULACION E INGESTA REAL
# ==========================================

def main():
    parser = argparse.ArgumentParser(
        description="Ingesta Bronze del proyecto Danper"
    )

    parser.add_argument(
        "--ejecutar",
        action="store_true",
        help="Cargar archivos realmente en HDFS"
    )

    args = parser.parse_args()

    print("===== BRONZE DANPER =====")

    if args.ejecutar:
        print("Modo: INGESTA REAL")
    else:
        print("Modo: SIMULACION - SIN ESCRITURA")

    destinos = preparar_inventario()

    print("Archivos locales:", len(destinos), flush=True)

    # Una unica consulta para inventariar HDFS.
    archivos_hdfs = obtener_archivos_hdfs()

    pendientes = []
    existentes = []
    categorias = Counter()

    # Revisar rutas y tamanos sin modificar HDFS.
    for destino, archivo in destinos.items():
        categoria = archivo.relative_to(BASE).parts[0]
        categorias[categoria] += 1

        if destino in archivos_hdfs:
            tamano_local = archivo.stat().st_size
            tamano_hdfs = archivos_hdfs[destino]

            if tamano_local != tamano_hdfs:
                raise ValueError(
                    "Existe un archivo con tamano diferente:\n"
                    f"Local: {archivo}\n"
                    f"HDFS: {destino}\n"
                    f"Local: {tamano_local} bytes\n"
                    f"HDFS: {tamano_hdfs} bytes\n"
                    "No se sobrescribira automaticamente."
                )

            existentes.append((archivo, destino))

        else:
            pendientes.append((archivo, destino))

    print("\n===== RESUMEN POR CATEGORIA =====")

    for categoria, cantidad in sorted(
        categorias.items()
    ):
        print(f"{categoria}: {cantidad}")

    print("\n===== REVISION =====")
    print("Ya existentes:", len(existentes))
    print("Pendientes:", len(pendientes))
    print("Total:", len(destinos))

    # Salir sin escribir en HDFS.
    if not args.ejecutar:
        print("\nSimulacion terminada.")
        print("No se modifico HDFS.")
        print(
            "Para realizar la ingesta:",
            "python3 scripts/ingesta_bronze.py --ejecutar"
        )
        return

    # Validar contenido de archivos existentes
    # antes de subir archivos nuevos.
    print("\nValidando archivos existentes...")

    for archivo, destino in existentes:
        if sha256_local(archivo) != sha256_hdfs(destino):
            raise ValueError(
                "El archivo existente tiene contenido "
                f"diferente: {destino}"
            )

    print(
        "Archivos existentes verificados:",
        len(existentes)
    )

    # Cargar solamente los archivos nuevos.
    print("\n===== CARGANDO ARCHIVOS =====")

    cargados = 0

    for numero, (archivo, destino) in enumerate(
        pendientes,
        start=1
    ):
        carpeta_hdfs = destino.rsplit("/", 1)[0]

        print(
            f"[{numero}/{len(pendientes)}] "
            f"{archivo.relative_to(BASE)}",
            flush=True
        )

        ejecutar([
            "hdfs", "dfs", "-mkdir", "-p",
            carpeta_hdfs
        ])

        # Subir sin reemplazar archivos.
        ejecutar([
            "hdfs", "dfs", "-put",
            archivo.as_uri(),
            destino
        ])

        # Comprobar contenido despues de subir.
        hash_local = sha256_local(archivo)
        hash_hdfs = sha256_hdfs(destino)

        if hash_local != hash_hdfs:
            raise RuntimeError(
                "Fallo la comprobacion SHA-256:\n"
                f"{destino}"
            )

        cargados += 1

    print("\n===== INGESTA FINALIZADA =====")
    print("Existentes verificados:", len(existentes))
    print("Nuevos cargados:", cargados)
    print("Total:", len(existentes) + cargados)
    print("Destino principal:", BRONZE)


if __name__ == "__main__":
    main()

