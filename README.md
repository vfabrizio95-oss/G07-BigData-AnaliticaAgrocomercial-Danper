# G07 - Big Data y Analítica Agrocomercial para Danper

## Aplicación en vivo: guía del evaluador

La plataforma está desplegada en AWS (cluster de 1 master y 3 workers en Amazon EC2, Amazon RDS y Amazon S3) y se puede probar sin instalar nada. La **URL** y la **contraseña** de la carga de datos están en el informe del proyecto (Anexo: guía del evaluador); aquí aparecen como `<URL>` y `<CONTRASEÑA>`.

| Qué | Dirección | Acceso |
|---|---|---|
| Tablero (Grafana) | `<URL>/` | Libre, solo lectura |
| Carga de datos nuevos | `<URL>/carga` | Usuario `admin` y `<CONTRASEÑA>` |
| Estado del pipeline | `<URL>/estado` | Libre; se actualiza sola cada 10 s |
| Estado en JSON | `<URL>/api/estado` | Libre |

**Prueba de punta a punta (unos 6 minutos):**

1. En `<URL>/estado`, anotar el **último dato de ingreso a planta** (por ejemplo, `2024-12`), los meses del **pronóstico vigente** y la fecha **«entrenado con datos hasta»** del modelo.
2. En `<URL>/carga`, ingresar con `admin` y la contraseña, elegir **6 meses** y pulsar **«Inyectar dato de prueba»**. Se cargan seis meses **simulados** de ingreso de materia prima a planta (alcachofa y espárrago), con el formato de la fuente oficial y marcados `DEMO`.
3. En `<URL>/estado`, la fase pasa de «esperando la sincronización con S3» a «procesando», con cada etapa (Bronze → Silver → Gold → Modelo (aplicar) → PostgreSQL) y sus segundos, y a «terminado» unos 4 minutos después (la detección tarda hasta 2 minutos: unos 6 en total).
4. Comprobar el resultado: el último dato y el pronóstico vigente avanzaron seis meses, y la fecha de entrenamiento del modelo **no cambió** (el modelo ya entrenado se aplica con `transform()`, no se reentrena). En el tablero, sin recargar la página, cambian «Último dato de ingreso a planta», el panel «Pronóstico vigente» y el ingreso real frente al plan anual.

La prueba se puede repetir: cada vez se cargan los meses siguientes (2, 4 o 6). También se pueden subir archivos propios en `<URL>/carga`, hasta 10 a la vez, que se procesan juntos en una sola corrida: un Excel `.xlsx` de ingreso a planta con el formato de la fuente (cuadro 7 o 64; hay ejemplos descargables en la misma página) o un PDF del Gran Mercado Mayorista de Lima con su nombre original de MIDAGRI (`...-DD-MM-AAAA.pdf`). Un archivo con otro formato se rechaza con un mensaje que explica el motivo.

El detalle de los campos de `/api/estado` está en [docs/guia_evaluador.md](docs/guia_evaluador.md). Para recrear la plataforma desde cero, seguir las secciones 7 en adelante (entorno local) y el despliegue en AWS.

## 1. Descripción del proyecto

Proyecto académico desarrollado para la asignatura Big Data y Analítica de Datos de la Universidad Privada Antenor Orrego (UPAO), durante el semestre 2026-20.

El proyecto consiste en el desarrollo de una plataforma de Big Data y Analítica Agrocomercial orientada a integrar información de producción agrícola, precios, costos, abastecimiento mayorista, actividad agroindustrial y exportaciones, tomando como empresa de estudio a Danper Trujillo S.A.C.

La solución utiliza información agrocomercial recopilada de fuentes externas e institucionales para generar conjuntos de datos procesados, indicadores y análisis que puedan apoyar la planificación del abastecimiento y la comercialización agrícola.

Los resultados corresponden a información de referencia y no representan necesariamente los registros operativos internos de Danper.

## 2. Objetivo del proyecto

Desarrollar una plataforma de Big Data y Analítica de Datos que permita recopilar, transformar, integrar y analizar información agrocomercial mediante Apache Hadoop HDFS y Apache Spark/PySpark, generando indicadores y resultados analíticos que apoyen la toma de decisiones.

## 3. Tecnologías utilizadas

| Tecnología | Versión | Función |
|---|---|---|
| Debian 12 / Ubuntu 24.04 | — | Sistema operativo (entornos probados) |
| OpenJDK | 11 | Ejecución de Hadoop y Spark |
| Apache Hadoop HDFS | 3.3.6 | Almacenamiento de datos |
| Apache Spark / PySpark | 3.5.1 | Procesamiento y transformación |
| Spark SQL | 3.5.1 | Consultas y agregaciones |
| Python | 3.11 | Scripts y análisis de datos |
| poppler-utils (`pdftotext`) | 24.02 | Lectura de los reportes PDF |
| Apache Parquet | Formato columnar | Almacenamiento de datos procesados |

Las bibliotecas de Python y sus versiones están en `requirements.txt`.

Los scripts no fijan el master de Spark: se define con `spark-submit --master` o con la variable `DANPER_SPARK_MASTER` (ver sección 7). Al ejecutarlos con `python`, PySpark usa `local[*]`.

## 4. Arquitectura del pipeline

La plataforma adopta una arquitectura Data Lake basada en tres capas:

**Bronze:** archivos originales de las fuentes recopiladas, conservados para permitir la revisión de su procedencia y eventual reprocesamiento.

**Silver:** conjuntos de datos limpios y estructurados, preparados para realizar transformaciones y operaciones analíticas.

**Gold:** tablas analíticas, dimensiones, hechos e indicadores generados mediante Apache Spark.

### Rutas de almacenamiento

| Capa | Ruta | Estado |
|---|---|---|
| Bronze | `/danper/bronze` | Verificada: 181 archivos (180 de la carga base + 1 reporte GMML incorporado de forma incremental), `fsck` HEALTHY |
| Silver | `/danper/silver` | Verificada: 11 tablas, 79 498 filas |
| Gold | `/danper/gold` | Verificada: 26/26 componentes |
| Calidad | `/danper/calidad` | Incidencias de agroindustria, costos, regionales y abastecimiento |

La URI de HDFS (por defecto `hdfs://localhost:9000`) y la carpeta raíz (`/danper`) se configuran en `scripts/config.py` mediante variables de entorno.

## 5. Fuentes de datos

El proyecto considera información relacionada con:

- Producción agrícola provincial de La Libertad.
- Encuesta Nacional Agropecuaria.
- Exportaciones aduaneras atribuidas a SUNAT.
- Exportaciones regionales por cultivo.
- Costos de jornales y servicios agrícolas.
- Actividad agroindustrial.
- Abastecimiento y precios de mercados mayoristas.

Las fuentes presentan diferentes periodos, formatos y niveles de detalle. Por ello, sus datos deben interpretarse según la cobertura y las definiciones originales.

Los archivos se organizaron en formatos como CSV, XLSX, XLS y PDF.

**Disponibilidad:** los datasets originales no se encuentran incluidos en este repositorio. Para reproducir el procesamiento desde los archivos originales es necesario disponer de los datasets recopilados y de las instrucciones de ingesta y limpieza correspondientes.

El inventario y la descripción de columnas se documentan en el diccionario de datos del proyecto.

## 6. Organización del repositorio

El repositorio contiene archivos de código y documentación organizados principalmente en las siguientes ubicaciones:

### Scripts

| Script | Función |
|---|---|
| `scripts/config.py` | Configuración central: rutas HDFS, carpeta de datasets y master de Spark |
| `scripts/inventario_bronze.py` | Genera `reportes/inventario_bronze.csv` (ruta, tamaño y SHA-256 de cada archivo) |
| `scripts/ingesta_bronze.py` | Carga los datasets locales en `/danper/bronze` verificando SHA-256 |
| `scripts/extractor_*.py` | Lectura de los Excel de producción, agroindustria y exportaciones regionales (los importan los scripts Silver) |
| `scripts/transformacion_*_silver.py` | Bronze → Silver, uno por fuente (9 scripts) |
| `scripts/calidad_silver.py` | Controles básicos sobre la producción Silver |
| `scripts/generar_documentacion_silver.py` | Genera `docs/silver/*.md` desde HDFS |
| `scripts/procesamiento_gold.py` | Silver → Gold: construcción (`--build-missing`) y auditoría (`--check`) |
| `scripts/control.py` | Tabla de control `/danper/control/archivos.csv`: qué archivos pasaron por cada capa |
| `scripts/publicar_postgres.py` | Gold → PostgreSQL (esquema `gold`) por JDBC: escribe en `gold_staging`, valida las filas y reemplaza las tablas en una sola transacción (el dashboard nunca ve una tabla vacía) |
| `scripts/run_pipeline.py` | Orquestador incremental Bronze → Silver → Gold → PostgreSQL (`--vigilar` para revisar la carpeta de datasets) |
| `scripts/prueba_escalabilidad.py` | Pruebas de escalabilidad y de caché con métricas de Spark (secciones 12 y 13) |
| `scripts/modelo_abastecimiento.py` | Pronóstico del ingreso de materia prima a planta con Spark MLlib frente a la línea base (sección 15) |

**Dos registros de archivos distintos:**

- **`/danper/control/archivos.csv` (en HDFS)** es el registro del pipeline. `run_pipeline.py` lo actualiza solo con cada archivo nuevo: guarda su SHA-256 y la fecha y hora en que pasó por Bronze, Silver, Gold y PostgreSQL. Así sabe qué falta procesar.
- **`reportes/inventario_bronze.csv` (en el repositorio)** es una foto documental de la carpeta de datasets. Se regenera a mano con `python scripts/inventario_bronze.py` y se sube a Git como evidencia. El pipeline no lo modifica, para no generar un commit con cada archivo nuevo.

Por eso, entre una regeneración y la siguiente, el inventario del repositorio puede tener menos archivos que HDFS. Por ejemplo, el reporte GMML del 21-09-2026 se procesó el 18/11/2026 (de Bronze a PostgreSQL en 2 min 22 s) y entró al inventario recién al regenerarlo el 20/11/2026.

### Dashboard

| Archivo | Función |
|---|---|
| `dashboard/docker-compose.yml` | Grafana 12.4.3 en Docker |
| `dashboard/grafana/provisioning/` | Conexión a PostgreSQL y carga automática del tablero |
| `dashboard/grafana/dashboards/danper.json` | Tablero "Danper – Analítica agrocomercial" |

### Notebooks

- `notebooks/01_ingesta_bronze.ipynb`: evidencia de la ingesta Bronze (180 archivos locales = 180 en HDFS, SHA-256 y `fsck`).
- `notebooks/01_pipeline_danper.ipynb`: exploración de los Excel de producción.
- `notebooks/procesamiento_gold.ipynb`: documentación y comprobación del procesamiento Gold.
- `notebooks/Optimizacion_Rendimiento.ipynb`: primera prueba de caché. Reemplazada por `scripts/prueba_escalabilidad.py --prueba cache`.
- `notebooks/prueba_escalabilidad.ipynb`: primera prueba de escalabilidad. Reemplazada por `scripts/prueba_escalabilidad.py`.
- `notebooks/Analisis_Exploratorio_Danper.ipynb`: análisis exploratorio y visualizaciones.
- `notebooks/Modelo_Base_Danper.ipynb`: primer modelo (scikit-learn, producción 2025). Reemplazado por `scripts/modelo_abastecimiento.py`.

### Documentación

- `docs/reporte_calidad_gold.md`: resultados de auditoría y limitaciones de calidad.
- `docs/reporte_escalabilidad_gold.md`: método, resultados e interpretación de las pruebas de escalabilidad y caché.
- `docs/evidencia_mapreduce.md`: fases de MapReduce (map, combiner, shuffle y reduce) en el plan de Spark de una agregación de Gold, con sus métricas.
- `docs/reporte_seguridad_plataforma.md`: diagnóstico de controles de seguridad.

## 7. Requisitos previos e instalación

1. Java (OpenJDK 11), Hadoop 3.3.6 con HDFS en funcionamiento y Spark 3.5.1.
2. `pdftotext`: `sudo apt install poppler-utils`.
3. Python 3.11 con las dependencias de `requirements.txt`.
4. Los datasets originales (no se incluyen en el repositorio) en `~/proyecto_danper/datasets`, con la estructura de `reportes/inventario_bronze.csv`.

Las variables `JAVA_HOME`, `HADOOP_HOME`, `HADOOP_CONF_DIR`, `SPARK_HOME` y el `PATH` de Hadoop y Spark deben definirse en `~/.profile` (no al final de `~/.bashrc`, que no se lee en shells no interactivos).

### Obtener el repositorio y el entorno

```bash
git clone https://github.com/vfabrizio95-oss/G07-BigData-AnaliticaAgrocomercial-Danper.git
cd G07-BigData-AnaliticaAgrocomercial-Danper
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configuración

Todos los scripts leen `scripts/config.py`. Los valores por defecto sirven para la instalación local; para otro entorno se cambian variables, no código:

| Variable | Por defecto | Uso |
|---|---|---|
| `DANPER_HDFS_URI` | `hdfs://localhost:9000` | NameNode de HDFS |
| `DANPER_HDFS_BASE` | `/danper` | Carpeta raíz del proyecto en HDFS |
| `DANPER_DATASETS` | `~/proyecto_danper/datasets` | Datasets locales de entrada |
| `DANPER_SPARK_MASTER` | (sin definir) | Master de Spark, p. ej. `yarn` o `spark://host:7077` |

### Comprobar las herramientas

```bash
java -version
hadoop version
spark-submit --version
pdftotext -v
```

### Iniciar HDFS

```bash
start-dfs.sh
hdfs dfsadmin -safemode wait
```

## 7.1 Ejecución completa Bronze → Silver → Gold

Desde la raíz del repositorio, con el entorno activado. Los scripts que admiten `--ejecutar` funcionan sin él en modo simulación (validan sin escribir).

```bash
# Bronze (simulación y carga)
python scripts/ingesta_bronze.py
python scripts/ingesta_bronze.py --ejecutar

# Silver
python scripts/transformacion_silver.py --ejecutar
python scripts/transformacion_exportaciones_danper_silver.py --ejecutar
python scripts/transformacion_exportaciones_regionales_silver.py
python scripts/transformacion_agroindustria_silver.py
python scripts/transformacion_costos_silver.py
python scripts/transformacion_abastecimiento_silver.py --ejecutar
python scripts/transformacion_mercado_productores_silver.py --ejecutar
python scripts/transformacion_ena_2025_silver.py --ejecutar
python scripts/transformacion_sostenibilidad_silver.py --ejecutar

# Gold
spark-submit scripts/procesamiento_gold.py --build-missing
spark-submit scripts/procesamiento_gold.py --check
```

Los scripts de exportaciones regionales, agroindustria y costos no tienen modo simulación: escriben (sobrescriben) su tabla Silver al ejecutarse. ENA y sostenibilidad no sobrescriben destinos existentes.

Tiempos de referencia medidos el 17/11/2026 en un equipo de 8 CPU y 15 GiB (Ubuntu 24.04, HDFS pseudodistribuido): Bronze ≈ 20 min (180 archivos, uno por uno), Silver 4,9 min, Gold 59 s (`--build-missing`) y 19 s (`--check`).

## 7.2 Dashboard en Grafana

Grafana lee el esquema `gold` de PostgreSQL (lo publica `scripts/publicar_postgres.py`) con un usuario de solo lectura y se refresca cada 5 s, así que muestra cada publicación del pipeline sin recargar la página. La conexión y el tablero se cargan solos desde `dashboard/grafana/` (provisioning): no hay que configurar nada a mano.

Requisitos: Docker con el plugin Compose y la base `danper` con Gold publicado.

**1. Usuario de solo lectura** (una vez):

```bash
sudo -u postgres createuser --pwprompt --no-superuser --no-createdb --no-createrole grafana_lector
psql -h localhost -d danper <<'EOF'
GRANT CONNECT ON DATABASE danper TO grafana_lector;
GRANT USAGE ON SCHEMA gold TO grafana_lector;
GRANT SELECT ON ALL TABLES IN SCHEMA gold TO grafana_lector;
ALTER DEFAULT PRIVILEGES IN SCHEMA gold GRANT SELECT ON TABLES TO grafana_lector;
EOF
```

El segundo comando lo ejecuta el dueño del esquema `gold` (el usuario que publica).

**2. Contraseña** en `dashboard/.env` (no se sube al repositorio):

```bash
read -rsp "Contraseña de grafana_lector: " P && printf 'DANPER_GRAFANA_PG_PASSWORD=%s\n' "$P" > dashboard/.env && chmod 600 dashboard/.env && unset P; echo
```

**3. Levantar y detener:**

```bash
cd dashboard
docker compose up -d     # http://localhost:3000  (admin / admin)
docker compose down
```

El primer arranque tarda unos minutos (Grafana crea su base interna).

| Variable | Por defecto | Uso |
|---|---|---|
| `DANPER_GRAFANA_PG_PASSWORD` | (obligatoria) | Contraseña de `grafana_lector` |
| `DANPER_GRAFANA_PG_HOST` | `localhost:5432` | Servidor PostgreSQL |
| `DANPER_GRAFANA_PG_DB` | `danper` | Base de datos |
| `DANPER_GRAFANA_PG_USER` | `grafana_lector` | Usuario de solo lectura |
| `DANPER_GRAFANA_ADDR` | `127.0.0.1` | IP donde escucha Grafana; en AWS `0.0.0.0` (limitar el puerto 3000 con el security group) |
| `DANPER_GRAFANA_ADMIN_PASSWORD` | `admin` | Contraseña inicial del administrador; cambiarla fuera del entorno local |

**KPI de abastecimiento** (primera fila del tablero). Apoyan la decisión de cuánta materia prima asegurar con proveedores terceros (sección 15). Los datos vienen de `scripts/modelo_abastecimiento.py`, que hay que ejecutar antes de publicar.

| KPI | Definición y fórmula | Frecuencia | Responsable |
|---|---|---|---|
| 1. Plan 2025 (t) | Volumen a asegurar en el año siguiente al último dato: promedio del mismo mes en los 3 últimos años válidos, con banda de ± WAPE histórico (`ml_plan_ingreso`) | Anual, al cargar datos nuevos | Planeamiento / Extensión agrícola |
| 2. Error WAPE | Suma de errores absolutos / suma real del método recomendado, validación 2019–2024 (`ml_metricas_modelo`) | Anual | Planeamiento |
| 3. Sesgo | (Pronóstico anual − real) / real. Negativo significa que se planifica menos de lo que llega. Meta: entre −5 % y +5 % | Anual | Planeamiento / Compras |
| 4. Pico ago–oct | Ingreso de agosto a octubre / ingreso del año, último año válido de cada cultivo. Indica la capacidad de planta y de compra que se necesita en campaña | Anual | Operaciones de planta |
| 5. Meta 2023 | Volumen logrado / meta de materia prima de proveedores (alcachofa 21 315 / 25 623 t; espárrago 5 965 / 6 117 t). Valor fijo tomado del Reporte de Sostenibilidad Danper 2023 | Anual | Compras |

La fila incluye además el plan 2025 por mes, el pronóstico frente al valor real de 2019–2024 y el error de cada método por año.

**Contenido del tablero:** KPI de abastecimiento, estado del pipeline (última publicación, filas y fecha del último reporte GMML, historial), abastecimiento y precios del GMML, exportaciones de Danper y regionales, producción e ingreso a planta agroindustrial, costos agrícolas por región y precios del Mercado de Productores. Filtros: cultivo y región.

**Demostración del pipeline incremental:** con `python scripts/run_pipeline.py --vigilar` en ejecución, copiar un PDF GMML nuevo a `~/proyecto_danper/datasets/abastecimiento/gmml_<año>/`. En unos 3 minutos cambian "Última publicación en PostgreSQL", "Registros de abastecimiento GMML" y "Último reporte GMML".

**Demostración con el modelo:** `python scripts/generar_demo_agroindustria.py --salida /tmp/demo --factor 1.3` crea Excel **simulados** de ingreso a planta (enero y febrero del año siguiente al último dato, marcados "DEMO"). Al copiarlos a `datasets/agroindustria/` (en AWS: subirlos a `s3://<bucket>/datasets/agroindustria/`), el pipeline los lleva hasta Gold, aplica el modelo guardado y cambian "Último dato de ingreso a planta", el panel "Pronóstico vigente" y el real frente al plan. El script explica cómo retirarlos después. En AWS, la ingesta automática se activa una vez con `sudo bash infra/aws/activar_ingesta.sh`.

**Portal público (AWS):** `sudo bash infra/aws/instalar_portal.sh` publica en una URL fija de CloudFront el tablero (`/`, solo lectura), la página de carga (`/carga`, con contraseña y el botón "Inyectar dato de prueba", que genera cada vez los dos meses siguientes) y el avance del pipeline (`/estado` y `/api/estado`). La prueba para el evaluador está en `docs/guia_evaluador.md`; los datos de prueba se retiran con `sudo bash infra/aws/retirar_demo.sh`.

## 8. Verificación del almacenamiento HDFS

Antes de procesar los datos es necesario comprobar que HDFS esté disponible y que existan los conjuntos Silver.

Listar los conjuntos Silver:

`hdfs dfs -ls /danper/silver`

Listar los componentes Gold:

`hdfs dfs -ls /danper/gold`

Estos comandos permiten consultar la estructura de almacenamiento sin modificar los datos.

### Conjuntos de entrada Silver

El script de procesamiento Gold utiliza los siguientes conjuntos:

| Conjunto | Ruta relativa a `/danper/silver` |
|---|---|
| Producción agrícola | `produccion` |
| Exportaciones regionales | `exportaciones/regionales` |
| Exportaciones Danper | `exportaciones/danper` |
| Agroindustria | `agroindustria` |
| Costos agrícolas | `costos` |
| Abastecimiento mayorista | `abastecimiento` |
| Precios de mercado de productores | `mercado_productores` |

Las entradas deben estar almacenadas en formato Parquet y presentar los esquemas esperados por el script.

## 9. Ejecución del procesamiento Gold

El procesamiento Gold está implementado en:

`scripts/procesamiento_gold.py`

Este script admite dos modos principales: verificación y construcción de componentes faltantes.

### 9.1. Verificar componentes existentes

Desde la raíz del repositorio, ejecutar:

`spark-submit scripts/procesamiento_gold.py --check`

Este modo comprueba que existan las 26 rutas, que cada componente tenga exactamente las columnas esperadas y al menos las filas de la carga base (se admiten más filas cuando ingresan datos nuevos).

No realiza escrituras en HDFS.

Si todos los componentes se encuentran correctamente, el programa muestra:

`AUDITORIA GOLD: 26/26 CORRECTOS. HDFS NO MODIFICADO.`

### 9.2. Construir componentes Gold faltantes

Cuando se dispone de los conjuntos Silver correctos y se necesita generar componentes Gold ausentes, se puede utilizar:

`spark-submit scripts/procesamiento_gold.py --build-missing`

Este modo crea únicamente los componentes ausentes y no sobrescribe las rutas Gold existentes.

**Precaución:** antes de utilizar `--build-missing`, comprobar que las entradas Silver, sus esquemas y los permisos de escritura correspondan al entorno previsto. Los conteos de referencia definidos en el código son mínimos de la carga base: una cantidad menor se considera pérdida de datos y detiene el proceso.

## 10. Resultados del procesamiento Gold

La implementación comprobada dispone de 26 componentes analíticos:

| Categoría | Cantidad |
|---|---:|
| Tablas analíticas | 7 |
| Tablas de dimensiones | 6 |
| Tablas de hechos | 7 |
| Tablas de KPI | 6 |
| **Total** | **26** |

Los resultados se encuentran almacenados en `/danper/gold`, mediante archivos Parquet.

La verificación de existencia y estructura de estos componentes no sustituye una validación completa de calidad semántica o procedencia de los datos.

## 11. Control de calidad

El análisis de calidad se documenta en:

`docs/reporte_calidad_gold.md`

Entre los principales hallazgos se identificaron valores faltantes en variables agrícolas, periodos incompletos, unidades de costos pendientes de confirmar y cobertura parcial de algunos indicadores.

Los valores nulos no se reemplazan automáticamente por cero, ya que podrían representar información no reportada.

Asimismo, las exportaciones regionales y los registros de exportación asociados a Danper se analizan por separado para evitar interpretaciones incorrectas.

## 12. Prueba de caché

`scripts/prueba_escalabilidad.py --prueba cache` prepara una tabla analítica de producción (pivot de las 7 variables por distrito, cultivo y mes) sobre Silver ×F y ejecuta 5 consultas de KPI sobre ella: sin caché, cada consulta vuelve a leer y transformar los datos desde HDFS; con caché, la tabla se guarda una vez en memoria. Cada modo se ejecuta como un programa de Spark independiente (proceso y memoria propios), con 1 ejecución de calentamiento y 3 mediciones. Antes de guardarla en caché, la tabla se junta en 2 particiones por núcleo: si se dejan las 200 particiones del shuffle, la caché resulta **más lenta** que no usarla, porque cada consulta paga 200 tareas pequeñas.

Resultados locales (mediana de 3 mediciones, 8 hilos; `reportes/escalabilidad/cache.csv`):

| Factor | Filas de entrada | Sin caché | Con caché | Reducción | Preparar la caché (una vez) |
|---|---:|---:|---:|---:|---:|
| ×1 | 78 515 | 1,80 s | 1,26 s | 30 % | 3,0 s |
| ×100 | 7,9 M | 4,25 s | 1,56 s | 63 % | 4,6 s |
| ×1000 | 78,5 M | 20,15 s | 1,92 s | **90 %** | 10,1 s |

La ventaja crece con el volumen: con caché, el tiempo de las consultas casi no depende del tamaño de los datos. En ×1000 la caché se paga desde la primera ejecución (10,1 + 1,9 s frente a 20,2 s). La reducción vale para consultas repetidas sobre la misma tabla, no para todo el pipeline.

Reemplaza a `notebooks/Optimizacion_Rendimiento.ipynb` (1,55 → 0,61 s), que medía con datos de ×1 y en otra máquina.

## 13. Prueba de escalabilidad

`scripts/prueba_escalabilidad.py` reemplaza a `notebooks/prueba_escalabilidad.ipynb` y al antiguo `procesamiento_gold_escalabilidad.py`, cuyos tiempos (54,98 / 55,03 / 53,35 s para ×1 / ×10 / ×100) no tenían respaldo en el repositorio y no eran comparables: las réplicas idénticas se fusionaban en los `distinct` y `pivot` de Gold, Silver pesaba solo 505 KB (×100 seguía siendo pequeño) y la memoria se medía con `psutil` en lugar de con Spark.

**Método**

- **Réplicas que no se fusionan:** Silver se replica ×1, ×10, ×100 y ×1000 en `/danper/pruebas_escalabilidad/silver_xF`. Cada copia lleva una columna `replica` que forma parte de todas las claves, y sus valores se alteran levemente. El script comprueba que las filas de salida sean exactamente F veces las de ×1.
- **Trabajo medido:** es representativo de Gold: pivot de producción y de exportaciones, agregaciones de agroindustria y Danper, ventana `lag` sobre costos, dimensión de tiempo con `join`, KPI anual y escritura de 6 tablas en HDFS.
- **Escenarios independientes:** cada escenario (un factor con un número de núcleos o de workers) se ejecuta como un programa de Spark separado, que Spark llama *aplicación*: arranca con memoria vacía y termina antes del siguiente. Así la memoria, la caché o el calentamiento de un escenario no favorecen al siguiente. No es un modelo ni hay entrenamiento: solo se mide el tiempo del mismo trabajo de Gold.
- **Repeticiones:** dentro de cada escenario, 1 ejecución de calentamiento (se registra, pero no se promedia) y 3 mediciones. Se reporta la mediana.
- **Métricas de Spark:** se toman de su API REST: tiempo de executors, shuffle, tareas y memoria JVM pico. Con `spark.eventLog.enabled` cada aplicación queda en `/danper/spark-events` y se puede revisar en el Spark History Server.
- **Resultados:** cada ejecución se agrega a `reportes/escalabilidad/escalabilidad.csv`, junto con el entorno en que se midió (núcleos, master y executores).

**Resultados locales** (Intel i7-6700HQ, 4 núcleos físicos y 8 hilos, 15 GB, HDFS de un nodo):

Volumen creciente con 8 hilos:

| Factor | Filas de entrada | Filas de salida | Tiempo (mediana) | Tiempo de executors | Shuffle | Memoria pico |
|---|---:|---:|---:|---:|---:|---:|
| ×1 | 78 515 | 11 208 | 4,8 s | 2,0 s | 0,7 MB | 347 MB |
| ×10 | 785 150 | 112 080 | 7,2 s | 8,7 s | 6,3 MB | 525 MB |
| ×100 | 7,9 M | 1,1 M | 10,3 s | 36,3 s | 57 MB | 1 556 MB |
| ×1000 | 78,5 M | 11,2 M | 32,4 s | 213 s | 574 MB | 2 100 MB |

Paralelismo creciente con ×1000:

| Hilos (`local[n]`) | Tiempo (mediana) | Aceleración |
|---:|---:|---:|
| 1 | 81,9 s | 1,0× |
| 2 | 50,2 s | 1,6× |
| 4 | 31,0 s | 2,6× |
| 8 | 32,4 s | 2,5× |

**Lectura**

- Con 1 000 veces más datos el tiempo crece unas 7 veces (4,8 → 32,4 s). En volúmenes pequeños domina el costo fijo de Spark (planificación y tareas); desde ×100 el trabajo real crece con el volumen, como muestra el tiempo de executors.
- Repartir el trabajo acelera 2,6× con 4 núcleos. De 4 a 8 hilos no mejora porque el equipo tiene 4 núcleos físicos (hyperthreading) y un solo disco y DataNode.
- **Esta es una validación local del método.** Las cifras finales se toman en el cluster AWS con el mismo script, variando 1, 2 y 3 workers:

```bash
DANPER_SPARK_MASTER=yarn python scripts/prueba_escalabilidad.py \
    --factores 1 10 100 1000 --executores 1 2 3 --entorno aws
```

**Cómo se ejecuta en el cluster AWS**

| Pieza | Local (validación) | Cluster AWS |
|---|---|---|
| Dónde corre el script | La misma PC | El master, que también aloja el driver de Spark, el ResourceManager de YARN, el NameNode y el History Server |
| Qué se varía | Hilos de una máquina (`--nucleos 1 2 4 8` → `local[n]`) | Workers que trabajan (`--executores 1 2 3` → `spark.executor.instances`, sin asignación dinámica) |
| Quién ejecuta las tareas | Hilos del mismo proceso | Executors en los workers (NodeManager), cada uno con los núcleos y la memoria de una máquina (`spark.executor.cores` y `spark.executor.memory` en `spark-defaults.conf`), para que 1, 2 o 3 executors equivalgan a 1, 2 o 3 workers |
| Datos | HDFS de un nodo | HDFS con 2 o 3 DataNodes y `dfs.replication=2`; las réplicas ×F se generan una vez en el cluster |
| Evidencia | CSV con `entorno=local` | CSV con `entorno=aws`; cada escenario aparece como una aplicación separada en la interfaz de YARN (puerto 8088, solo por túnel) y en el Spark History Server, con las tareas que corrió cada worker |

Lo que se espera ver en AWS es que, con ×1000, el tiempo baje al pasar de 1 a 2 y 3 workers, porque el map y el reduce se reparten entre más máquinas. A diferencia de la PC local, cada worker agrega núcleos físicos, disco y DataNode propios.

Generar las réplicas es un paso aparte (se registra en el CSV con fase `generacion`): ×1000 tarda 51 s y ocupa 238 MB en HDFS. Los datos replicados solo se usan para medir rendimiento; no entran en el análisis ni en el modelo.

## 14. Análisis exploratorio

El notebook `notebooks/Analisis_Exploratorio_Danper.ipynb` contiene consultas y visualizaciones construidas sobre datos procesados de la capa Gold.

El análisis permite examinar el comportamiento de la producción agrícola por periodo, cultivo y ubicación geográfica, según los registros disponibles.

Los resultados utilizan información de referencia y no deben presentarse como producción interna de Danper.

## 15. Modelo predictivo de abastecimiento

### Problema de negocio

Danper compra alcachofa y espárrago a proveedores terceros y debe programar ese volumen con anticipación. En 2023 la compra de alcachofa quedó **16,8 % por debajo de la meta** (25 623 t planificadas, 21 315 t logradas; espárrago −2,5 %), según el Reporte de Sostenibilidad Danper 2023.

El modelo pronostica, **con 3 meses de anticipación**, el ingreso mensual de materia prima a las plantas agroindustriales de La Libertad (Gold `agroindustria_mensual`, proceso `INGRESO`: alcachofa "para procesar" y espárrago "natural", fuente GRALL-OIA, 2010–2024). Es el volumen regional que las empresas del sector deben asegurar.

### Datos

- 360 meses (2 cultivos × 15 años), de los cuales **312 son válidos**.
- Se tratan como faltantes los años completos en cero (espárrago 2016, alcachofa 2017–2018), que son vacíos del registro y no producción nula.
- Espárrago 2024 es una copia celda a celda de 2023 en el Excel original, por lo que también se excluye.
- Espárrago 2017 es bajo (40 742 t) pero se conserva: coincide con el Niño Costero de ese año.

### Método

| | Descripción |
|---|---|
| Línea base `naive_anual` | Mismo mes del año anterior |
| Línea base `prom_3a` | Promedio del mismo mes en los 3 años anteriores |
| `gbt`, `rf`, `lineal` | `GBTRegressor`, `RandomForestRegressor` y `LinearRegression` (elastic net) de Spark MLlib |

- **Variables**, todas conocidas al momento de planificar: cultivo, mes, tamaño estacional del mes, tendencia de los últimos 3 meses observados frente al año anterior, el mismo mes 1 y 2 años antes respecto del promedio, y la tendencia de las exportaciones regionales del cultivo.
- **Objetivo:** los modelos pronostican cuánto se aparta el mes de su nivel estacional (log de la razón), con cada mes ponderado por sus toneladas. Luego se convierte a toneladas. Así se evita que los árboles queden limitados a los valores vistos al entrenar.
- **Validación hacia adelante por año:** para cada año de 2019 a 2024 se entrena solo con los meses anteriores y se pronostica ese año. Son 6 cortes y 132 meses de prueba, todos los métodos sobre los mismos meses.
- **Métricas en toneladas:**
  - MAE (error medio mensual).
  - WAPE (suma de errores absolutos / suma real).
  - Error anual (cuánto se desvía el total del año).

### Resultados

Horizonte 3 meses, años de prueba 2019–2024 (`reportes/modelo/metricas.csv`, también por año):

| Método | Alcachofa WAPE | Espárrago WAPE | Total MAE | Total WAPE | Error anual |
|---|---:|---:|---:|---:|---:|
| **`prom_3a` (línea base)** | **41,6 %** | 29,7 % | **3 272 t** | **36,9 %** | −16,0 % |
| `naive_anual` (línea base) | 45,6 % | **27,0 %** | 3 385 t | 38,1 % | −10,4 % |
| `lineal` (MLlib) | 43,9 % | 30,8 % | 3 428 t | 38,6 % | −19,0 % |
| `rf` (MLlib) | 44,4 % | 35,3 % | 3 616 t | 40,7 % | −21,2 % |
| `gbt` (MLlib) | 47,2 % | 34,8 % | 3 747 t | 42,2 % | −23,3 % |

**Ningún modelo de aprendizaje automático supera a la línea base estacional.** También se probó modelar las toneladas directamente y un horizonte de 1 mes, con el mismo resultado.

### Interpretación

- La serie depende de choques anuales que no están en su propia historia: clima (Niño Costero 2017) y decisiones de siembra y mercado. Por ejemplo, la alcachofa ingresó 139 mil t en 2022, 91 mil t en 2023 y 156 mil t en 2024.
- Con 312 meses válidos no hay muestra suficiente para que un modelo aprenda esos choques. Este resultado se reporta tal cual en lugar de ajustar el modelo mirando los años de prueba.
- **Todos los métodos subestiman el volumen anual (−10 % a −23 %)**: planificar solo con la historia lleva a asegurar menos materia prima de la que finalmente llega.
- **Recomendación:** usar `prom_3a` como base de la planificación y revisar su sesgo cada temporada. Para mejorar el pronóstico hacen falta variables que anticipen los choques, como intenciones de siembra, superficie instalada o clima, con varios años de historia.

### Ejecución y salidas

```bash
python scripts/modelo_abastecimiento.py              # evaluar, entrenar y guardar (~3 min)
python scripts/modelo_abastecimiento.py --aplicar    # solo aplicar el modelo guardado (~30 s)
```

**Entrenar una vez, aplicar muchas.** El modo por defecto evalúa los métodos y luego entrena el `Pipeline` de MLlib `lineal` (el mejor de MLlib) con toda la historia y lo guarda con `PipelineModel.save()`. Con `--aplicar` no se entrena nada: se carga el modelo y se aplica `.transform()` a lo que haya en Gold. `run_pipeline.py` ejecuta `--aplicar` después de Gold cada vez que llegan datos nuevos, así que el resultado del modelo llega al tablero sin reentrenar.

| Salida | Contenido |
|---|---|
| `/danper/gold/ml_prediccion_ingreso` | Valor real y pronóstico de cada método por mes de prueba |
| `/danper/gold/ml_metricas_modelo` | MAE, WAPE y error anual por cultivo, método y año |
| `/danper/gold/ml_plan_ingreso` | Plan del año en curso con `prom_3a`, su banda y el ingreso real de los meses que ya llegaron |
| `/danper/gold/ml_pronostico_vigente` | Los 3 meses siguientes al último dato: `prom_3a` y el modelo guardado |
| `/danper/modelos/ingreso_lineal_h3` | `PipelineModel` entrenado y su ficha (fecha y último mes de entrenamiento) |
| `reportes/modelo/metricas.csv` | Copia de las métricas, versionada en el repositorio |

El primer modelo (`notebooks/Modelo_Base_Danper.ipynb`, scikit-learn sobre producción 2025, R² 0,30) queda como antecedente: usaba un solo año de datos y tampoco superaba a una referencia simple.

## 16. Seguridad

El diagnóstico de seguridad se encuentra en:

`docs/reporte_seguridad_plataforma.md`

Se verificaron permisos básicos en HDFS y se identificaron limitaciones relacionadas con autenticación y cifrado.

El entorno académico utiliza una configuración que no debe asumirse equivalente a una infraestructura empresarial segura.

Para una implementación productiva se recomienda fortalecer los controles de acceso, las credenciales y la protección de datos almacenados y transmitidos.

## 17. Estado de reproducibilidad

El repositorio permite consultar los scripts, notebooks y reportes técnicos del proyecto.

El 17/11/2026 se reconstruyó el pipeline completo desde los datasets originales en un entorno nuevo (Ubuntu 24.04): los 180 archivos coincidieron con el inventario por SHA-256 y se obtuvieron los mismos resultados documentados en Bronze (180 archivos), Silver (11 tablas, 79 498 filas) y Gold (26/26).

Pendiente:

1. Procedimiento de obtención de los datasets originales y condiciones de reutilización de cada fuente.
2. Carga incremental (datos nuevos sin reprocesar todo) y orquestación de punta a punta.
3. Despliegue en un cluster distribuido.

## 18. Repositorio y documentación

Repositorio:

https://github.com/vfabrizio95-oss/G07-BigData-AnaliticaAgrocomercial-Danper

Rama principal: `main`. El desarrollo se integra en `develop` y desde ahí se pasa a `main`.

El proyecto se encuentra en desarrollo académico y sus resultados tienen fines de investigación y aprendizaje.

## 19. Equipo de trabajo

Proyecto desarrollado por el Grupo 07 de la Universidad Privada Antenor Orrego.

- Castañeda Castillo Estanis Vidal.
- Olguín Vasquez Danna.
- Rubiños Angulo Víctor Fabrizio.
- Vera Perez Xiomara.

Asignatura: Big Data y Analítica de Datos.

Periodo académico: 2026-20.
