# Procesamiento Silver - Proyecto Danper

## Objetivo

Transformar datos de HDFS Bronze en conjuntos Parquet estructurados, trazables y utilizables por la capa Gold.

## Arquitectura

`HDFS Bronze -> Python/PySpark -> HDFS Silver -> Gold`

La solución se ejecuta en infraestructura local (on-premise).

## Tablas procesadas

| Tabla | Descripción | Registros | Ruta Silver |
|---|---|---:|---|
| `produccion` | Producción agrícola regional | 65,922 | `/danper/silver/produccion` |
| `exportaciones_danper` | Exportaciones de Danper | 1,124 | `/danper/silver/exportaciones/danper` |
| `exportaciones_regionales` | Exportaciones regionales | 2,043 | `/danper/silver/exportaciones/regionales` |
| `abastecimiento` | Abastecimiento GMML | 66 | `/danper/silver/abastecimiento` |
| `mercado_productores` | Mercado de Productores | 756 | `/danper/silver/mercado_productores` |
| `agroindustria` | Agroindustria | 3,134 | `/danper/silver/agroindustria` |
| `costos` | Costos agrícolas | 6,292 | `/danper/silver/costos` |
| `ena_produccion` | ENA 2025 - Producción | 49 | `/danper/silver/ena_2025/produccion` |
| `ena_insumos` | ENA 2025 - Insumos | 23 | `/danper/silver/ena_2025/insumos` |
| `ena_uso_tierra` | ENA 2025 - Uso de tierra | 77 | `/danper/silver/ena_2025/uso_tierra` |
| `sostenibilidad` | Indicadores de sostenibilidad Danper | 12 | `/danper/silver/sostenibilidad/danper_indicadores` |

**Total:** 11 tablas y 79,498 filas.

El total representa filas de distintas fuentes y granularidades; no debe interpretarse como productores únicos.

## Scripts

Los procesos de transformación están en `scripts/`.
Algunos utilizan modo de validación antes de escribir en HDFS.
Revisar las opciones de cada script antes de ejecutarlo nuevamente.

## Documentos complementarios

- `diccionario_datos.md`: campos y tipos Spark.
- `reporte_calidad.md`: controles y valores ausentes.

## Precauciones

- No sobrescribir Parquet sin realizar un respaldo.
- ENA 2025 es información muestral, no operaciones internas de Danper.
- Los indicadores ambientales tienen diferentes años y alcances.
- Algunos datos originales carecen de valores o metadatos.
