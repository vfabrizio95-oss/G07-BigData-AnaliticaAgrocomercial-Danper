# Pruebas de escalabilidad y de caché del procesamiento Gold — Danper

Script: `scripts/prueba_escalabilidad.py`. Resultados por ejecución:
`reportes/escalabilidad/escalabilidad.csv` y `reportes/escalabilidad/cache.csv`.
Evidencia de Spark: event log en `/danper/spark-events` (Spark History Server).

## Objetivo

Medir cómo cambia el tiempo del procesamiento Silver → Gold cuando crece el
volumen de datos y cuando crece el paralelismo disponible, y cuánto reduce la
caché de Spark el tiempo de consultas repetidas.

## Entorno de esta medición (validación local)

- Equipo: Intel Core i7-6700HQ (4 núcleos físicos, 8 hilos), 15 GB de RAM, Ubuntu 24.04.
- Apache Spark 3.5.1 en modo `local[n]`, driver con 4 GB.
- HDFS 3.3.6 de un solo nodo.
- Las cifras finales se toman en el cluster AWS con el mismo script, variando
  1, 2 y 3 workers (`--executores 1 2 3 --entorno aws`).

## Método

1. **Réplicas de Silver ×1, ×10, ×100 y ×1000** de las cinco fuentes principales
   (producción, exportaciones regionales, agroindustria, costos y exportaciones
   de Danper), en `/danper/pruebas_escalabilidad/silver_xF`.
   - Cada copia lleva una columna `replica` que forma parte de todas las claves de
     agrupación, ventana y join. Sus valores se alteran levemente (+0 % a +6 %).
   - Así las réplicas no se fusionan en los `distinct` y `pivot` y el trabajo
     crece con el factor.
   - El script comprueba que las filas de salida sean exactamente F veces las de ×1.
2. **Trabajo medido:** es representativo de Gold.
   - Pivot de producción (7 variables) y de exportaciones regionales.
   - Agregaciones de agroindustria y de exportaciones de Danper.
   - Ventana `lag` sobre costos.
   - Dimensión de tiempo y su `join`.
   - KPI anual de producción.
   - Escritura de 6 tablas en HDFS.
3. **Escenarios independientes y repeticiones:** cada escenario (un factor con
   un número de núcleos o de workers) se ejecuta como un programa de Spark
   separado, que Spark llama *aplicación*: arranca con memoria vacía y termina
   antes del siguiente. Así la memoria, la caché o el calentamiento de un
   escenario no favorecen al siguiente. No es un modelo ni hay entrenamiento:
   se mide el tiempo del mismo trabajo de Gold.
   - Dentro de cada escenario: 1 ejecución de calentamiento (registrada, pero
     no promediada) y 3 mediciones. Se reporta la mediana, el mínimo y el máximo.
4. **Métricas:**
   - El tiempo de pared se mide en el script.
   - El tiempo de executors, el shuffle, las tareas y la memoria JVM pico se
     leen de la API REST de monitoreo de Spark, no de `psutil`.
5. **Prueba de caché:** sobre una tabla analítica de producción (pivot de las
   7 variables) se ejecutan 5 consultas de KPI, una vez sin caché y otra con caché.
   - El tiempo de llenar la caché se mide aparte.
   - Antes de guardarla en caché, la tabla se junta en 2 particiones por núcleo.
     Con las 200 particiones que deja el shuffle, la caché resultó más lenta que
     no usarla (5,5 s frente a 3,1 s en ×10).

## Resultados

### Volumen creciente (8 hilos)

| Factor | Filas de entrada | Filas de salida | Tiempo (mediana) | Tiempo de executors | Shuffle escrito | Memoria pico |
|---|---:|---:|---:|---:|---:|---:|
| ×1 | 78 515 | 11 208 | 4,8 s | 2,0 s | 0,7 MB | 347 MB |
| ×10 | 785 150 | 112 080 | 7,2 s | 8,7 s | 6,3 MB | 525 MB |
| ×100 | 7 851 500 | 1 120 800 | 10,3 s | 36,3 s | 57 MB | 1 556 MB |
| ×1000 | 78 515 000 | 11 208 000 | 32,4 s | 213 s | 574 MB | 2 100 MB |

### Paralelismo creciente (×1000)

| Hilos | Tiempo (mediana) | Tiempo de executors | Aceleración |
|---:|---:|---:|---:|
| 1 | 81,9 s | 79 s | 1,0× |
| 2 | 50,2 s | 88 s | 1,6× |
| 4 | 31,0 s | 107 s | 2,6× |
| 8 | 32,4 s | 213 s | 2,5× |

### Caché (8 hilos)

| Factor | Sin caché | Con caché | Reducción | Preparar la caché |
|---|---:|---:|---:|---:|
| ×1 | 1,80 s | 1,26 s | 30 % | 3,0 s |
| ×100 | 4,25 s | 1,56 s | 63 % | 4,6 s |
| ×1000 | 20,15 s | 1,92 s | 90 % | 10,1 s |

### Generación de réplicas (paso aparte, no incluido en los tiempos anteriores)

| Factor | Filas | Tamaño en HDFS | Tiempo |
|---|---:|---:|---:|
| ×1 | 78 515 | 0,3 MB | 12,2 s |
| ×10 | 785 150 | 2,9 MB | 7,5 s |
| ×100 | 7 851 500 | 28,7 MB | 12,7 s |
| ×1000 | 78 515 000 | 238,3 MB | 51,0 s |

## Interpretación

- **Volumen:** con 1 000 veces más datos, el tiempo crece unas 7 veces.
  - Hasta ×10 domina el costo fijo de Spark: planificar, lanzar tareas y escribir archivos.
  - Desde ×100 el trabajo real crece con el volumen, como muestran el tiempo de
    executors y el shuffle, que crecen casi 10 veces por cada salto.
- **Paralelismo:** pasar de 1 a 4 núcleos acelera 2,6 veces. De 4 a 8 hilos no
  hay mejora, porque el equipo tiene 4 núcleos físicos (los otros 4 son
  hyperthreading) y un solo disco y DataNode. El tiempo de executors se duplica
  porque los hilos compiten por los mismos núcleos.
- **Caché:** su ventaja crece con el volumen; con caché, el tiempo de las
  consultas casi no depende del tamaño de los datos. En ×1000, preparar la caché
  más una ejecución (12 s) ya cuesta menos que una ejecución sin caché (20 s).

## Cómo se ejecuta en el cluster AWS

- **Dónde corre:** el script se ejecuta en el master, donde están el driver de
  Spark, el ResourceManager de YARN, el NameNode y el History Server. Con
  `DANPER_SPARK_MASTER=yarn`, cada escenario es una aplicación de YARN cuyas
  tareas corren en executors de los workers.
- **Qué se varía:** `--executores 1 2 3` fija `spark.executor.instances` sin
  asignación dinámica.
- **Un executor por worker:** cada executor se dimensiona con los núcleos y la
  memoria de una máquina (`spark.executor.cores` y `spark.executor.memory` en
  `spark-defaults.conf`), así que 1, 2 o 3 executors equivalen a 1, 2 o 3
  workers.
- **Datos:** HDFS con 2 o 3 DataNodes y `dfs.replication=2`. Las réplicas ×F
  se generan una vez en el cluster.
- **Evidencia:**
  - CSV con `--entorno aws`.
  - Cada escenario como aplicación separada en la interfaz de YARN (puerto
    8088, solo por túnel, nunca abierto a internet).
  - El Spark History Server, que muestra qué worker ejecutó cada tarea.
- **Resultado esperado:** con ×1000, el tiempo baja al pasar de 1 a 2 y 3
  workers, porque cada worker agrega núcleos físicos, disco y DataNode propios.
  En la PC local, en cambio, los hilos 5 a 8 compartían los mismos 4 núcleos y
  el mismo disco.

## Limitaciones

- Medición local en una sola máquina: valida el método, no la escalabilidad
  horizontal. Esa se mide en AWS variando el número de workers.
- Se mide la etapa Silver → Gold con un trabajo representativo, no las 26
  tablas de `procesamiento_gold.py` ni el recorrido desde Bronze. Las réplicas
  romperían las validaciones de unicidad de Gold.
- Las réplicas reproducen la estructura de los datos reales, no su diversidad.
  Solo sirven para medir rendimiento y no se usan en el análisis ni en el modelo.
- La reducción por caché vale para consultas repetidas sobre la misma tabla,
  no para la duración de todo el pipeline.

## Prueba anterior (reemplazada)

La versión previa de este reporte informaba 54,98 / 55,03 / 53,35 s para ×1 /
×10 / ×100, medidos en una máquina virtual de 5 CPU y 8 GiB. Esas cifras no se
conservan porque:

- No estaban respaldadas por ningún script, notebook ni log del repositorio.
- Las réplicas eran copias idénticas que se fusionaban en los `distinct` y `pivot`
  de Gold, así que ×100 hacía casi el mismo trabajo que ×1.
- Silver pesaba 505 KB, de modo que incluso ×100 era un volumen pequeño y el
  tiempo lo dominaba el arranque de Spark.
- La memoria se midió con `psutil` (proceso Python y sistema), no con métricas
  de Spark, y por eso la RAM de ×100 salía menor que la de ×1.
