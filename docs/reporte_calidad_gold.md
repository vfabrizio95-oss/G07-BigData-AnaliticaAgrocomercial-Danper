# Informe de calidad de datos - Zona Gold

**Proyecto:** Big Data y Analítica Agrocomercial - Danper

**Fecha de generación:** 2026-10-11 15:03

**Entorno:** Hadoop HDFS y Apache Spark (on-premise)

## 1. Objetivo

Documentar la calidad, cobertura y principales limitaciones de las fuentes procesadas en la zona Gold del Data Lake.

## 2. Auditoría del almacenamiento

La auditoría verificó la existencia, lectura en formato Parquet y cantidad esperada de registros de 26 componentes Gold:

- 7 tablas analíticas.
- 6 dimensiones.
- 7 tablas de hechos.
- 6 tablas de indicadores KPI.

**Resultado:** 26 componentes correctos y 0 componentes con problemas en las comprobaciones realizadas.

Esta auditoría no sustituye las pruebas de calidad semántica o la validación externa de las fuentes.

## 3. Hallazgos de calidad

### 3.1. Producción agrícola

**Hallazgo:** 165 registros de 2024 sin producción reportada.

**Impacto:** No es posible calcular la producción de 2024 con esta fuente.

**Recomendación:** Mostrar el valor como no disponible; evitar comparaciones anuales de producción con 2025.

### 3.2. Precio en chacra

**Hallazgo:** 165 registros de 2024 sin precio reportado.

**Impacto:** No puede calcularse el precio promedio de 2024.

**Recomendación:** Mantener los valores nulos y mostrar cobertura.

### 3.3. Rendimiento agrícola

**Hallazgo:** 561 registros sin rendimiento disponible.

**Impacto:** No se puede evaluar el rendimiento con esta columna.

**Recomendación:** Excluir este indicador hasta disponer de datos válidos.

### 3.4. Exportaciones regionales

**Hallazgo:** 38 registros sin volumen exportado.

**Impacto:** Algunos totales de volumen tienen cobertura incompleta.

**Recomendación:** Presentar los contadores de registros disponibles.

### 3.5. Exportaciones Danper

**Hallazgo:** 68 registros correspondientes a 2026.

**Impacto:** La información de 2026 representa un periodo parcial.

**Recomendación:** No comparar directamente con años completos.

### 3.6. Costos agrícolas

**Hallazgo:** 6292 registros con unidad NO_CONFIRMADA.

**Impacto:** No se puede asegurar la unidad de los valores.

**Recomendación:** Mantener separados los tipos de costo y no atribuir unidades no verificadas.

### 3.7. Agroindustria

**Hallazgo:** 978 registros con cantidad igual a cero.

**Impacto:** Los ceros pueden afectar agregaciones y promedios.

**Recomendación:** Conservar los ceros originales y analizar cada proceso por separado.

### 3.8. Abastecimiento mayorista

**Hallazgo:** 28 registros sin ingreso de hoy.

**Impacto:** Los promedios de ingreso se basan en una cobertura parcial.

**Recomendación:** Mostrar el porcentaje de cobertura junto al indicador.

## 4. Consideraciones para los indicadores

- Los valores nulos no representan necesariamente cero.
- Los KPI se calculan sobre los registros disponibles.
- Los precios de diferentes unidades comerciales no se comparan directamente.
- Las exportaciones regionales y las exportaciones propias de Danper se analizan por separado.
- En agroindustria, INGRESO, PRODUCCION, UTILIZACION y VENTA representan procesos diferentes.
- Los ingresos mayoristas son reportes puntuales, no acumulados anuales.
- Los datos de 2026 deben tratarse como parciales.

## 5. Conclusión

Los componentes Gold se encuentran almacenados y fueron verificados con respecto a las cantidades esperadas. Sin embargo, existen limitaciones de completitud, cobertura temporal y unidades de medida que deben considerarse en el dashboard y los análisis posteriores.

El procesamiento conserva los datos originales y documenta las restricciones para evitar interpretaciones incorrectas.
