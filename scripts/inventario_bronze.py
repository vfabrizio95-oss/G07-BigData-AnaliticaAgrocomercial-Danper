from pathlib import Path
from collections import Counter, defaultdict
import hashlib
import csv

BASE = Path.home() / "proyecto_danper/datasets"
SALIDA = Path("reportes/inventario_bronze.csv")


def calcular_sha256(archivo):
    sha = hashlib.sha256()

    with archivo.open("rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            sha.update(bloque)

    return sha.hexdigest()


def main():
    archivos = sorted(
        archivo for archivo in BASE.rglob("*")
        if archivo.is_file()
    )

    if not archivos:
        raise FileNotFoundError(
            f"No hay archivos en {BASE}"
        )

    registros = []
    grupos_hash = defaultdict(list)

    for archivo in archivos:
        relativo = archivo.relative_to(BASE)
        sha256 = calcular_sha256(archivo)

        registro = {
            "categoria": relativo.parts[0],
            "ruta_relativa": relativo.as_posix(),
            "nombre_archivo": archivo.name,
            "formato": archivo.suffix.lower(),
            "tamano_bytes": archivo.stat().st_size,
            "sha256": sha256,
        }

        registros.append(registro)
        grupos_hash[sha256].append(relativo.as_posix())

    SALIDA.parent.mkdir(parents=True, exist_ok=True)

    with SALIDA.open("w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(
            f,
            fieldnames=[
                "categoria",
                "ruta_relativa",
                "nombre_archivo",
                "formato",
                "tamano_bytes",
                "sha256",
            ],
        )

        escritor.writeheader()
        escritor.writerows(registros)

    print("===== INVENTARIO BRONZE =====")
    print("Total de archivos:", len(registros))
    print("Inventario:", SALIDA)

    print("\nArchivos por categoría:")
    conteos = Counter(r["categoria"] for r in registros)

    for categoria, cantidad in sorted(conteos.items()):
        print(f"{categoria}: {cantidad}")

    duplicados = [
        rutas for rutas in grupos_hash.values()
        if len(rutas) > 1
    ]

    print("\nGrupos con contenido duplicado:", len(duplicados))

    for grupo in duplicados:
        print("\nContenido repetido:")
        for ruta in grupo:
            print(" -", ruta)


if __name__ == "__main__":
    main()
