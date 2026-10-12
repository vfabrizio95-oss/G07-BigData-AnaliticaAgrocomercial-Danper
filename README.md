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
| Debian GNU/Linux | 12 | Sistema operativo |
| Apache Hadoop HDFS | 3.3.6 | Almacenamiento de datos |
| Apache Spark / PySpark | 3.5.1 | Procesamiento y transformación |
| Spark SQL | 3.5.1 | Consultas y agregaciones |
| Python | 3.11.2 | Scripts y análisis de datos |
| JupyterLab | 4.6.3 | Desarrollo y ejecución de notebooks |
| Git | 2.39.5 | Control de versiones |
| Apache Parquet | Formato columnar | Almacenamiento de datos procesados |

Se utilizaron también bibliotecas de Python como Pandas, Openpyxl y Scikit-learn para tareas de lectura, preparación y modelado. Las versiones específicas de estas bibliotecas deberán verificarse en el entorno utilizado.

El procesamiento Gold se ha ejecutado con Spark configurado en modo local. Aunque Hadoop YARN forma parte de las tecnologías consideradas, su utilización efectiva como gestor de recursos del pipeline todavía requiere verificación.

## 4. Arquitectura del pipeline

La plataforma adopta una arquitectura Data Lake basada en tres capas:

**Bronze:** archivos originales de las fuentes recopiladas, conservados para permitir la revisión de su procedencia y eventual reprocesamiento.

**Silver:** conjuntos de datos limpios y estructurados, preparados para realizar transformaciones y operaciones analíticas.

**Gold:** tablas analíticas, dimensiones, hechos e indicadores generados mediante Apache Spark.

### Rutas de almacenamiento

| Capa | Ruta | Estado |
|---|---|---|
| Bronze | Pendiente de confirmar | Ubicación definitiva no verificada en HDFS |
| Silver | `/danper/silver` | Verificada |
| Gold | `/danper/gold` | Verificada |

Las rutas se utilizan sobre el sistema HDFS configurado en `hdfs://localhost:9000`.

**Importante:** la arquitectura de tres capas describe el diseño del proyecto. La existencia y el funcionamiento de Bronze deben acreditarse con la evidencia de ingesta correspondiente.

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

- `scripts/procesamiento_gold.py`: construcción y verificación de componentes analíticos Gold.
- `scripts/procesamiento_gold_escalabilidad.py`: procesamiento experimental Gold utilizado en escenarios de escalabilidad.

### Notebooks

- `notebooks/procesamiento_gold.ipynb`: documentación y comprobación del procesamiento Gold.
- `notebooks/Optimizacion_Rendimiento.ipynb`: comparación de rendimiento de Spark sin caché y con caché.
- `notebooks/prueba_escalabilidad.ipynb`: pruebas experimentales de escalabilidad.
- `notebooks/Analisis_Exploratorio_Danper.ipynb`: análisis exploratorio y visualizaciones.
- `notebooks/Modelo_Base_Danper.ipynb`: desarrollo y evaluación inicial del modelo predictivo.

### Documentación

- `docs/reporte_calidad_gold.md`: resultados de auditoría y limitaciones de calidad.
- `docs/reporte_escalabilidad_gold.md`: mediciones de tiempos y recursos.
- `docs/reporte_seguridad_plataforma.md`: diagnóstico de controles de seguridad.

No todos los archivos de configuración o dependencias están todavía centralizados en un procedimiento único de instalación.

## 7. Requisitos previos

Para ejecutar la etapa de procesamiento Silver→Gold, se requiere:

1. Un sistema compatible con las herramientas utilizadas en el proyecto.
2. Apache Hadoop HDFS configurado y en funcionamiento.
3. Apache Spark con soporte para Hadoop.
4. Python y PySpark compatibles con la instalación de Spark.
5. Acceso a los conjuntos Silver almacenados en HDFS.
6. Recursos suficientes de CPU, memoria y almacenamiento.

Las pruebas documentadas se realizaron sobre Debian 12, utilizando Spark 3.5.1 y Hadoop 3.3.6.

### Obtener el repositorio

Clonar el proyecto:

`git clone https://github.com/vfabrizio95-oss/G07-BigData-AnaliticaAgrocomercial-Danper.git`

Ingresar al directorio:

`cd G07-BigData-AnaliticaAgrocomercial-Danper`

Seleccionar la rama de integración:

`git checkout develop`

### Comprobar las herramientas

Consultar las versiones instaladas:

`hadoop version`

`python3 --version`

`git --version`

`/opt/spark-3.5.1-bin-hadoop3/bin/spark-submit --version`

La ruta de Spark corresponde a la instalación identificada durante el desarrollo. Si se utiliza otra instalación, debe adaptarse al entorno disponible.

Las bibliotecas adicionales de Python deberán instalarse según las dependencias reales de cada notebook. Se encuentra pendiente publicar un archivo de dependencias con sus versiones verificadas.

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

`/opt/spark-3.5.1-bin-hadoop3/bin/spark-submit scripts/procesamiento_gold.py --check`

Este modo comprueba las rutas existentes y sus cantidades de filas y columnas esperadas.

No realiza escrituras en HDFS.

Si todos los componentes se encuentran correctamente, el programa muestra:

`AUDITORIA GOLD: 26/26 CORRECTOS. HDFS NO MODIFICADO.`

### 9.2. Construir componentes Gold faltantes

Cuando se dispone de los conjuntos Silver correctos y se necesita generar componentes Gold ausentes, se puede utilizar:

`/opt/spark-3.5.1-bin-hadoop3/bin/spark-submit scripts/procesamiento_gold.py --build-missing`

Este modo crea únicamente los componentes ausentes y no sobrescribe las rutas Gold existentes.

**Precaución:** antes de utilizar `--build-missing`, comprobar que las entradas Silver, sus esquemas y los permisos de escritura correspondan al entorno previsto. Los conteos esperados están definidos en el código y corresponden al conjunto utilizado durante las pruebas del proyecto.

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

## 15. Modelo predictivo base

El notebook `notebooks/Modelo_Base_Danper.ipynb` documenta un modelo inicial de regresión para estimar la producción agrícola utilizando variables de cultivo, provincia, distrito y mes.

Se utilizó un conjunto de producción de 2025, con una separación temporal entre entrenamiento y prueba.

### Resultados iniciales

| Métrica | Resultado |
|---|---:|
| MAE | 1.868,54 toneladas |
| RMSE | 3.086,99 toneladas |
| R² | 0,2989 |

El modelo se considera una referencia inicial para posteriores mejoras. En la evaluación efectuada, una regresión de referencia basada en la mediana obtuvo un MAE inferior, por lo que el modelo lineal todavía no demuestra una mejora respecto de esa alternativa sencilla.

Las métricas corresponden a las pruebas documentadas y deben comprobarse nuevamente al reproducir el notebook en un entorno preparado desde cero.

## 16. Seguridad

El diagnóstico de seguridad se encuentra en:

`docs/reporte_seguridad_plataforma.md`

Se verificaron permisos básicos en HDFS y se identificaron limitaciones relacionadas con autenticación y cifrado.

El entorno académico utiliza una configuración que no debe asumirse equivalente a una infraestructura empresarial segura.

Para una implementación productiva se recomienda fortalecer los controles de acceso, las credenciales y la protección de datos almacenados y transmitidos.

## 17. Estado de reproducibilidad

El repositorio permite consultar los scripts, notebooks y reportes técnicos del proyecto.

Actualmente se ha documentado la verificación del procesamiento Gold a partir de conjuntos Silver ya preparados.

Para garantizar la reproducción integral desde los datos originales, todavía se requiere completar o verificar:

1. El procedimiento de obtención de todos los datasets originales.
2. La ubicación efectiva de la capa Bronze.
3. Los scripts y el orden de ejecución de Bronze→Silver.
4. Las instrucciones de instalación con versiones verificadas de las dependencias Python.
5. Una prueba de reproducción completa en un entorno limpio.
6. Las condiciones de acceso y reutilización de cada fuente original.

Hasta completar estas verificaciones, la reproducibilidad debe considerarse **parcial y documentada principalmente para Silver→Gold**.

## 18. Repositorio y documentación

Repositorio:

https://github.com/vfabrizio95-oss/G07-BigData-AnaliticaAgrocomercial-Danper

Rama de integración:

`develop`

Los resultados del proyecto deben contrastarse con los notebooks, los scripts y la documentación técnica incluidos en esta rama.

El proyecto se encuentra en desarrollo académico y sus resultados tienen fines de investigación y aprendizaje.

## 19. Equipo de trabajo

Proyecto desarrollado por el Grupo 07 de la Universidad Privada Antenor Orrego.

- Castañeda Castillo Estanis Vidal.
- Olguín Vasquez Danna.
- Rubiños Angulo Víctor Fabrizio.
- Vera Perez Xiomara.

Asignatura: Big Data y Analítica de Datos.

Periodo académico: 2026-20.
