# Ingesta de archivos agrícolas originales a HDFS Bronze

from pathlib import Path
import subprocess

ORIGEN = Path.home() / "proyecto_danper/datasets/produccion"
DESTINO = "/danper/bronze/produccion/"

def ejecutar_ingesta():
    archivos = sorted(ORIGEN.glob("*.xlsx"))

    if not archivos:
        raise FileNotFoundError(
            f"No se encontraron archivos Excel en {ORIGEN}"
        )

    print("Archivos encontrados:", len(archivos))

    subprocess.run(
        ["hdfs", "dfs", "-mkdir", "-p", DESTINO],
        check=True
    )

    for archivo in archivos:
        print("Cargando:", archivo.name)

        subprocess.run(
            [
                "hdfs", "dfs", "-put", "-f",
                archivo.as_uri(),
                DESTINO
            ],
            check=True
        )

    print("Ingesta finalizada correctamente.")


if __name__ == "__main__":
    ejecutar_ingesta()
