"""Avance del pipeline en archivos JSON pequeños (config.ESTADO).

run_pipeline.py escribe pipeline.json en cada etapa y modelo_abastecimiento.py
escribe modelo.json al aplicar el modelo. El portal web (web/portal.py) los
lee para la página /estado, de modo que una persona o un evaluador
automático puede seguir el recorrido de un archivo sin entrar al servidor.
"""
from datetime import datetime, timezone
import json
import os

import config


def ahora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def escribir(nombre, datos):
    """Escribe ESTADO/<nombre>.json de forma atómica (nunca queda a medias)."""
    try:
        config.ESTADO.mkdir(parents=True, exist_ok=True)
        destino = config.ESTADO / f"{nombre}.json"
        temporal = destino.with_suffix(".tmp")
        temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2, default=str),
                            encoding="utf-8")
        os.replace(temporal, destino)
    except OSError as error:  # el estado es informativo: nunca detiene el pipeline
        print(f"Aviso: no se pudo escribir el estado {nombre}: {error}")


def leer(nombre):
    try:
        return json.loads((config.ESTADO / f"{nombre}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
