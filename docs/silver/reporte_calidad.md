# Reporte de calidad - Capa Silver

## Alcance

Auditoría de 11 tablas mediante PySpark.
Los controles no reemplazan la validación semántica de negocio.

## produccion

- Registros: **65922**
- Columnas: **13**
- Duplicados exactos: **0**
- Columnas totalmente nulas: Ninguna
- Valores nulos parciales: Ninguno

## exportaciones_danper

- Registros: **1124**
- Columnas: **12**
- Duplicados exactos: **0**
- Columnas totalmente nulas: Ninguna
- Valores nulos parciales: `pagina_origen`: 138

## exportaciones_regionales

- Registros: **2043**
- Columnas: **10**
- Duplicados exactos: **0**
- Columnas totalmente nulas: Ninguna
- Valores nulos parciales: Ninguno

## abastecimiento

- Registros: **66**
- Columnas: **14**
- Duplicados exactos: **0**
- Columnas totalmente nulas: Ninguna
- Valores nulos parciales: `ingreso_ayer_t`: 38, `ingreso_hoy_t`: 28, `promedio_ingreso_7dias_t`: 63, `promedio_ingreso_4semanas_t`: 49, `tendencia`: 48

## mercado_productores

- Registros: **756**
- Columnas: **13**
- Duplicados exactos: **0**
- Columnas totalmente nulas: Ninguna
- Valores nulos parciales: Ninguno

## agroindustria

- Registros: **3134**
- Columnas: **10**
- Duplicados exactos: **0**
- Columnas totalmente nulas: Ninguna
- Valores nulos parciales: Ninguno

## costos

- Registros: **6292**
- Columnas: **8**
- Duplicados exactos: **0**
- Columnas totalmente nulas: Ninguna
- Valores nulos parciales: Ninguno

## ena_produccion

- Registros: **49**
- Columnas: **25**
- Duplicados exactos: **0**
- Columnas totalmente nulas: Ninguna
- Valores nulos parciales: `P105`: 2, `P105_DIB`: 2, `P220_1_VAL`: 1, `P220_1_PRE_KG`: 1, `P220_2_VAL`: 46, `P220_2_PRE_KG`: 46

## ena_insumos

- Registros: **23**
- Columnas: **19**
- Duplicados exactos: **0**
- Columnas totalmente nulas: P235_VAL, P235_PRE_KG
- Valores nulos parciales: `P237_VAL`: 8, `P237_PRE_KG`: 8

## ena_uso_tierra

- Registros: **77**
- Columnas: **21**
- Duplicados exactos: **0**
- Columnas totalmente nulas: Ninguna
- Valores nulos parciales: `P115_LOTE`: 17

## sostenibilidad

- Registros: **12**
- Columnas: **11**
- Duplicados exactos: **0**
- Columnas totalmente nulas: Ninguna
- Valores nulos parciales: Ninguno

## Controles numéricos

En el Paso 82 se comprobaron valores negativos en campos no negativos, NaN e infinitos en columnas numéricas.
**Resultado observado: 0 incidencias numéricas.**

## Limitaciones conocidas

- Exportaciones Danper: 138 registros de 2026 sin `pagina_origen`.
- Abastecimiento: indicadores no disponibles en parte de los reportes originales.
- ENA insumos: `P235_VAL` y `P235_PRE_KG` sin valores disponibles en la selección.
- ENA usa factores de expansión que requieren tratamiento metodológico antes de estimaciones poblacionales.
- La ausencia de duplicados exactos no garantiza ausencia de duplicados según claves de negocio.
- Sostenibilidad: conservar año del indicador, año del reporte, página y alcance.
