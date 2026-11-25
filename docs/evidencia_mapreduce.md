# Evidencia de MapReduce en el procesamiento Gold — Danper

Spark no reemplaza la idea de MapReduce: la ejecuta en memoria y en un solo
plan. Cada agregación de Gold sigue las fases del paradigma, y el plan físico
de Spark (`explain`) y las métricas de sus etapas (API de monitoreo) lo
muestran. Esta evidencia se tomó el 23/11/2026 en local (Spark 3.5.1,
`local[*]` con 8 hilos, HDFS de un nodo).

## Fases de MapReduce en una agregación de Gold

Ejemplo: las toneladas por cultivo, año y proceso a partir del ingreso mensual
de Silver. Es una versión simplificada del KPI anual de agroindustria
(`kpi_agroindustria_anual` en `scripts/procesamiento_gold.py`), que además
agrupa por presentación y une las dimensiones de cultivo y tiempo. El patrón
de fases es el mismo.

```python
df = (spark.read.parquet("hdfs://localhost:9000/danper/silver/agroindustria")
      .withColumn("cultivo", F.upper(F.trim("cultivo")))           # map
      .filter(F.col("cultivo").isin("ESPARRAGO", "ALCACHOFA")))    # map
kpi = (df.groupBy("cultivo", "anio", "proceso")                    # shuffle por clave
         .agg(F.sum("cantidad_t").alias("t"),                      # combiner + reduce
              F.count("*").alias("meses")))
kpi.explain()
```

Plan físico que produce Spark (se lee de abajo hacia arriba):

```text
HashAggregate(keys=[cultivo, anio, proceso], functions=[sum(cantidad_t), count(1)])                  <- REDUCE
+- Exchange hashpartitioning(cultivo, anio, proceso, 200)                                            <- SHUFFLE
   +- HashAggregate(keys=[cultivo, anio, proceso], functions=[partial_sum(cantidad_t), partial_count(1)]) <- COMBINER
      +- Project [anio, cantidad_t, upper(trim(cultivo)) AS cultivo, proceso]                        <- MAP
         +- Filter upper(trim(cultivo)) IN (ESPARRAGO, ALCACHOFA)                                    <- MAP
            +- FileScan parquet [...] Location: hdfs://localhost:9000/danper/silver/agroindustria    <- lectura de HDFS
```

| Fase | Operador en el plan | Qué hace en Danper |
|---|---|---|
| **Map** | `FileScan`, `Filter`, `Project` | Cada tarea lee un bloque de HDFS, normaliza el cultivo y descarta los que no son espárrago ni alcachofa. No necesita datos de otras tareas |
| **Combiner** | `HashAggregate (partial_sum, partial_count)` | Cada tarea suma localmente sus filas por (cultivo, año, proceso) antes de enviarlas |
| **Shuffle** | `Exchange hashpartitioning` | Envía cada clave a la tarea que la reduce. Todas las filas de una misma clave llegan a la misma tarea |
| **Reduce** | `HashAggregate (sum, count)` | Suma los parciales de cada clave y produce el total |

## Métricas de las etapas (API de monitoreo de Spark)

| Datos | Etapa map (tareas) | Filas leídas | Filas enviadas al shuffle | Etapa reduce (tareas) | Filas resultado | Tiempo |
|---|---:|---:|---:|---:|---:|---:|
| Silver real | 8 | 3 134 | 187 | 1 | 120 | 2,0 s |
| Silver ×1000 (réplicas de la prueba de escalabilidad) | 8 | 3 134 000 | 120 000 | 3 | 120 000 | 2,8 s |

**Lectura de la tabla:**

- **El combiner reduce el tráfico de red** en 94 % con los datos reales
  (3 134 → 187 filas) y en 96 % con ×1000 (3,1 millones → 120 000 filas):
  cada tarea envía sus sumas parciales, no cada fila.
- **El map es paralelo:** 8 tareas leen bloques distintos de HDFS al mismo
  tiempo. En un cluster, YARN reparte esas tareas entre los workers y prefiere
  el nodo que guarda cada bloque (localidad del dato).
- **El reduce se ajusta al volumen.** El plan pide 200 particiones de shuffle,
  pero la ejecución adaptativa de Spark (AQE) las junta según los datos: 1
  tarea con los datos reales y 3 con ×1000.
- **Mil veces más datos solo suman 0,8 s,** porque el trabajo se reparte en
  paralelo y el combiner mantiene pequeño lo que viaja por la red.

## Dónde más aparece el patrón en el proyecto

| Paso | Map | Shuffle y reduce |
|---|---|---|
| `procesamiento_gold.py`: pivot de producción | Normalizar el cultivo y filtrar periodos | `groupBy(provincia, distrito, cultivo, periodo).pivot(variable)` |
| `procesamiento_gold.py`: exportaciones regionales | Filtrar cultivos y meses válidos | `groupBy(cultivo, anio, mes).pivot(indicador)` |
| `procesamiento_gold.py`: KPI anuales | Seleccionar columnas | `groupBy(...).agg(sum, avg, countDistinct)` |
| `modelo_abastecimiento.py`: métricas del modelo | Calcular el error de cada mes | `groupBy(cultivo, metodo, anio).agg(...)` |
| `prueba_escalabilidad.py`: trabajo Gold ×F | Igual que Gold, con la columna `replica` | Las mismas agregaciones, con `replica` en la clave |

## En el cluster AWS

El mismo código corre sin cambios con `DANPER_SPARK_MASTER=yarn`:

- Las tareas del map se reparten entre los NodeManagers de los workers.
- El shuffle viaja por la red entre workers.
- El reduce corre en los executors que YARN asigne.

La evidencia se guarda de dos formas:

- **Spark History Server:** el event log (`/danper/spark-events`) muestra cada
  etapa, sus tareas y en qué worker corrió cada una.
- **Esta misma tabla de métricas:** tomada con la API de monitoreo, con 1, 2 y
  3 workers.

## Cómo reproducir

```bash
python - <<'EOF'
import sys; sys.path.insert(0, "scripts")
import config
from pyspark.sql import SparkSession, functions as F
spark = SparkSession.builder.config(map=config.SPARK_CONF).getOrCreate()
df = (spark.read.parquet(config.hdfs(config.SILVER + "/agroindustria"))
      .withColumn("cultivo", F.upper(F.trim("cultivo")))
      .filter(F.col("cultivo").isin("ESPARRAGO", "ALCACHOFA")))
kpi = df.groupBy("cultivo", "anio", "proceso").agg(F.sum("cantidad_t"), F.count("*"))
kpi.explain()
kpi.collect()   # ver las etapas en http://localhost:4040 (pestaña Stages)
EOF
```
