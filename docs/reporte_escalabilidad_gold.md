# Prueba de escalabilidad del procesamiento Gold — Danper

## Objetivo

Evaluar el comportamiento del procesamiento Silver → Gold al aumentar
el volumen de los siete conjuntos de datos de entrada mediante réplicas
de datos reales, utilizando factores de 1, 10 y 100.

## Entorno

- Sistema operativo: Debian 12.
- Procesamiento: Apache Spark 3.5.1.
- Almacenamiento: Hadoop HDFS.
- Infraestructura: máquina virtual on-premise.
- Recursos: 5 CPU virtuales y aproximadamente 8 GiB de RAM.
- Salidas: 26 componentes Gold por escenario.

## Resultados

| Indicador | x1 | x10 | x100 |
|---|---:|---:|---:|
| Componentes Gold | 26 | 26 | 26 |
| Tiempo (segundos) | 54.98 | 55.03 | 53.35 |
| Pico RAM sistema (GiB) | 5.42 | 5.59 | 5.36 |
| Pico RAM procesos (MiB) | 1063.24 | 1152.34 | 954.01 |
| Pico CPU sistema (%) | 83.9 | 76.8 | 84.5 |
| Código de salida | 0 | 0 | 0 |

Los valores de CPU y RAM corresponden a máximos observados durante
muestreos periódicos. La RAM del sistema incluye procesos ajenos a
Spark; la medición de procesos comprende el proceso Python y sus hijos
observados durante la ejecución.

## Interpretación

Las tres ejecuciones terminaron satisfactoriamente, con duraciones
cercanas a 55 segundos. En esta prueba no se observó un crecimiento
proporcional del tiempo respecto al factor de replicación.

Este comportamiento puede estar influido por el costo fijo de iniciar
Spark, la reducción de filas mediante agrupaciones y la repetición de
registros con las mismas claves.

Los datos replicados se utilizaron exclusivamente para medir rendimiento
y no deben utilizarse para análisis, entrenamiento de modelos ni
conclusiones de negocio.

## Limitaciones

- Se evaluó la etapa Silver → Gold, no el recorrido completo
  Bronze → Silver → Gold.
- Las réplicas conservan los valores originales y no representan
  la diversidad de nuevos registros reales.
- Para esta prueba se relajó la validación de unicidad de las tablas
  de hechos experimentales. El script original no fue modificado.
- Las ejecuciones no incluyen el tiempo de preparación de las réplicas.
- Los tiempos y recursos pueden variar según la carga de la máquina.
- No se identificó el límite exacto de capacidad de una sola máquina:
  únicamente se comprobó que los escenarios ensayados finalizaron.

## Conclusión

El procesamiento Gold logró generar sus 26 componentes con los tres
volúmenes de prueba. Los tiempos observados no evidenciaron degradación
proporcional al factor de replicación dentro del rango evaluado.

Los resultados muestran capacidad para ejecutar las cargas ensayadas
en el entorno disponible, pero no permiten afirmar escalabilidad
indefinida ni extrapolar el comportamiento a datos nuevos o al
pipeline completo desde Bronze.
