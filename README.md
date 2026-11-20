# G07 - Big Data y Analítica Agrocomercial para Danper

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
| Bronze | `/danper/bronze` | Verificada: 180 archivos, `fsck` HEALTHY |
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
| `scripts/procesamiento_gold_escalabilidad.py` | Variante de Gold para los escenarios de escalabilidad |
| `scripts/control.py` | Tabla de control `/danper/control/archivos.csv`: qué archivos pasaron por cada capa |
| `scripts/publicar_postgres.py` | Gold → PostgreSQL (esquema `gold`) por JDBC, para el dashboard |
| `scripts/run_pipeline.py` | Orquestador incremental Bronze → Silver → Gold → PostgreSQL (`--vigilar` para revisar la carpeta de datasets) |
| `scripts/modelo_abastecimiento.py` | Pronóstico del ingreso de materia prima a planta con Spark MLlib frente a la línea base (sección 15) |

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
- `notebooks/Optimizacion_Rendimiento.ipynb`: comparación de rendimiento de Spark sin caché y con caché.
- `notebooks/prueba_escalabilidad.ipynb`: pruebas experimentales de escalabilidad.
- `notebooks/Analisis_Exploratorio_Danper.ipynb`: análisis exploratorio y visualizaciones.
- `notebooks/Modelo_Base_Danper.ipynb`: primer modelo (scikit-learn, producción 2025). Reemplazado por `scripts/modelo_abastecimiento.py`.

### Documentación

- `docs/reporte_calidad_gold.md`: resultados de auditoría y limitaciones de calidad.
- `docs/reporte_escalabilidad_gold.md`: mediciones de tiempos y recursos.
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

**Contenido del tablero:** estado del pipeline (última publicación, filas y fecha del último reporte GMML, historial), abastecimiento y precios del GMML, exportaciones de Danper y regionales, producción e ingreso a planta agroindustrial, costos agrícolas por región y precios del Mercado de Productores. Filtros: cultivo y región.

**Demostración del pipeline incremental:** con `python scripts/run_pipeline.py --vigilar` en ejecución, copiar un PDF GMML nuevo a `~/proyecto_danper/datasets/abastecimiento/gmml_<año>/`. En unos 3 minutos cambian "Última publicación en PostgreSQL", "Registros de abastecimiento GMML" y "Último reporte GMML".

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

## 12. Optimización del rendimiento

El notebook `notebooks/Optimizacion_Rendimiento.ipynb` documenta una prueba de consultas repetidas sobre datos de producción agrícola almacenados en Silver.

Se comparó la ejecución sin caché y con caché de Apache Spark.

| Indicador | Resultado |
|---|---:|
| Tiempo promedio sin caché | 1,5480 segundos |
| Tiempo promedio con caché | 0,6090 segundos |
| Reducción observada | 60,66 % |

La comparación corresponde a las condiciones específicas del experimento y excluye el tiempo inicial necesario para preparar los datos en caché.

Por ello, el resultado no representa una reducción del 60,66 % en la duración de todo el pipeline.

## 13. Prueba de escalabilidad

El notebook `notebooks/prueba_escalabilidad.ipynb` documenta las pruebas de escalabilidad mediante factores de replicación ×1, ×10 y ×100.

Los datos replicados se utilizaron únicamente para medir rendimiento. No se emplearon en el análisis exploratorio ni en el entrenamiento del modelo.

### Resultados

| Indicador | ×1 | ×10 | ×100 |
|---|---:|---:|---:|
| Componentes Gold generados | 26 | 26 | 26 |
| Tiempo de ejecución (s) | 54,98 | 55,03 | 53,35 |
| Pico de RAM del sistema (GiB) | 5,42 | 5,59 | 5,36 |
| Pico de CPU del sistema (%) | 83,9 | 76,8 | 84,5 |

Las pruebas evaluaron la etapa **Silver→Gold**. No incluyen el recorrido completo desde los archivos originales hasta las tres capas.

Los tiempos observados no permiten determinar el límite máximo de escalabilidad de la infraestructura ni garantizar que nuevas fuentes reales presenten el mismo comportamiento.

Las rutas experimentales se organizaron bajo `/danper/pruebas_escalabilidad/`, separadas de los datos utilizados para análisis y modelado.

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
python scripts/modelo_abastecimiento.py              # horizonte 3, pruebas 2019-2024 (~2 min)
python scripts/modelo_abastecimiento.py --horizonte 1
```

| Salida | Contenido |
|---|---|
| `/danper/gold/ml_prediccion_ingreso` | Valor real y pronóstico de cada método por mes de prueba |
| `/danper/gold/ml_metricas_modelo` | MAE, WAPE y error anual por cultivo, método y año |
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
