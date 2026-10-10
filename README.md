# G07 - Big Data y Analítica Agrocomercial para Danper

## Descripción del proyecto

Desarrollo de una plataforma de Big Data y Analítica Agrocomercial para Danper Trujillo S.A.C., orientada a integrar información de producción agrícola, precios, costos, abastecimiento mayorista, agroindustria y exportaciones.

## Objetivo

Construir un pipeline de datos reproducible que permita recopilar, limpiar, transformar e integrar información agrocomercial para apoyar la planificación del abastecimiento y la comercialización.

## Tecnologías utilizadas

- Python y PySpark 3.5.1
- Apache Hadoop HDFS 3.3.6
- Hadoop YARN
- JupyterLab
- Pandas y Openpyxl
- Debian 12

## Arquitectura del pipeline

- **Bronze:** almacenamiento de datos originales.
- **Silver:** limpieza y transformación de datos.
- **Gold:** integración de información e indicadores agrocomerciales.

## Estructura del repositorio

- `notebooks/`: exploración y pruebas.
- `scripts/`: código del pipeline.
- `config/`: configuración de ejecución.
- `docs/`: documentación y diccionario de datos.
- `resultados/`: métricas y evidencias.

## Estado del proyecto

En desarrollo. Actualmente se realiza la inspección de los archivos de producción agrícola correspondientes a la campaña 2024–2025.

## Fuentes de datos

Información agrocomercial procedente de fuentes institucionales como MIDAGRI, INEI y SUNAT, según disponibilidad y verificación de procedencia.

Los datasets originales se almacenan localmente y no se incluyen en este repositorio.
