# Diccionario de datos - Capa Silver

Generado a partir de los esquemas reales almacenados en HDFS.
Las descripciones no confirmadas se indican como pendientes.

## Producción agrícola regional

**Tabla:** `produccion`

**Ruta HDFS:** `/danper/silver/produccion`

| Campo | Tipo Spark | Descripción | Nulos |
|---|---|---|---:|
| `provincia` | `string` | Provincia de referencia | 0 |
| `distrito` | `string` | Distrito de referencia | 0 |
| `codigo_cultivo` | `string` | Código del cultivo en la fuente | 0 |
| `cultivo` | `string` | Nombre del cultivo | 0 |
| `variable` | `string` | Variable registrada en la fuente | 0 |
| `columna_origen` | `int` | Columna de origen | 0 |
| `mes_origen` | `string` | Mes indicado en la fuente original | 0 |
| `valor` | `double` | Valor numérico del indicador | 0 |
| `archivo_origen` | `string` | Archivo original de procedencia | 0 |
| `posicion_mensual` | `int` | Posición del mes en el archivo original | 0 |
| `anio` | `int` | Año del registro | 0 |
| `mes_numero` | `int` | Número de mes | 0 |
| `periodo` | `date` | Período de referencia | 0 |

## Exportaciones de Danper

**Tabla:** `exportaciones_danper`

**Ruta HDFS:** `/danper/silver/exportaciones/danper`

| Campo | Tipo Spark | Descripción | Nulos |
|---|---|---|---:|
| `ruc` | `string` | Registro Unico de Contribuyentes del exportador | 0 |
| `exportador` | `string` | Nombre o razon social del exportador | 0 |
| `mes` | `string` | Mes de referencia | 0 |
| `agente` | `string` | Agente registrado en la operacion aduanera | 0 |
| `aduana` | `string` | Dependencia aduanera registrada | 0 |
| `pais` | `string` | Pais registrado en la operacion de exportacion | 0 |
| `fob_usd` | `double` | Valor FOB en dólares estadounidenses | 0 |
| `pagina_origen` | `string` | Página de origen disponible en la fuente | 138 |
| `archivo_origen` | `string` | Archivo original de procedencia | 0 |
| `numero_mes` | `int` | Número de mes | 0 |
| `anio` | `int` | Año del registro | 0 |
| `periodo` | `date` | Período de referencia | 0 |

## Exportaciones regionales

**Tabla:** `exportaciones_regionales`

**Ruta HDFS:** `/danper/silver/exportaciones/regionales`

| Campo | Tipo Spark | Descripción | Nulos |
|---|---|---|---:|
| `anio` | `bigint` | Año del registro | 0 |
| `archivo_origen` | `string` | Archivo original de procedencia | 0 |
| `cultivo` | `string` | Nombre del cultivo | 0 |
| `fila_excel` | `bigint` | Número de fila de Excel de origen | 0 |
| `hoja_origen` | `string` | Hoja del Excel original | 0 |
| `indicador` | `string` | Nombre del indicador | 0 |
| `mes` | `string` | Mes de referencia | 0 |
| `numero_mes` | `bigint` | Número de mes | 0 |
| `unidad` | `string` | Unidad de medida del valor | 0 |
| `valor` | `double` | Valor numérico del indicador | 0 |

## Abastecimiento GMML

**Tabla:** `abastecimiento`

**Ruta HDFS:** `/danper/silver/abastecimiento`

| Campo | Tipo Spark | Descripción | Nulos |
|---|---|---|---:|
| `fecha_reporte` | `string` | Fecha del reporte | 0 |
| `mercado` | `string` | Nombre del mercado mayorista de origen | 0 |
| `producto` | `string` | Nombre del producto reportado | 0 |
| `ingreso_ayer_t` | `double` | Ingreso reportado del dia anterior, toneladas | 38 |
| `ingreso_hoy_t` | `double` | Ingreso reportado del dia actual, toneladas | 28 |
| `promedio_ingreso_7dias_t` | `double` | Promedio de ingreso de siete dias, toneladas | 63 |
| `promedio_ingreso_4semanas_t` | `double` | Promedio de ingreso de cuatro semanas, toneladas | 49 |
| `unidad_medida` | `string` | Unidad de medida original | 0 |
| `equivalencia_kg` | `double` | Equivalencia de la unidad comercial en kilogramos | 0 |
| `precio_ayer_soles` | `double` | Precio reportado para el día anterior, en soles | 0 |
| `precio_hoy_soles` | `double` | Precio reportado para el día actual, en soles | 0 |
| `precio_7dias_soles` | `double` | Precio de referencia de siete días, en soles | 0 |
| `tendencia` | `string` | Tendencia reportada en el documento original | 48 |
| `archivo_origen` | `string` | Archivo original de procedencia | 0 |

## Mercado de Productores

**Tabla:** `mercado_productores`

**Ruta HDFS:** `/danper/silver/mercado_productores`

| Campo | Tipo Spark | Descripción | Nulos |
|---|---|---|---:|
| `fecha_reporte` | `date` | Fecha del reporte | 0 |
| `anio` | `int` | Año del registro | 0 |
| `mes_numero` | `int` | Número de mes | 0 |
| `mercado` | `string` | Nombre del mercado mayorista de origen | 0 |
| `categoria` | `string` | Categoria comercial del producto | 0 |
| `producto` | `string` | Nombre del producto reportado | 0 |
| `unidad_medida` | `string` | Unidad de medida original | 0 |
| `precio_7dias_soles` | `double` | Precio de referencia de siete días, en soles | 0 |
| `precio_ayer_soles` | `double` | Precio reportado para el día anterior, en soles | 0 |
| `precio_hoy_soles` | `double` | Precio reportado para el día actual, en soles | 0 |
| `variacion_porcentaje` | `double` | Variación porcentual reportada | 0 |
| `archivo_origen` | `string` | Archivo original de procedencia | 0 |
| `ruta_bronze` | `string` | Ruta del archivo original en HDFS Bronze | 0 |

## Agroindustria

**Tabla:** `agroindustria`

**Ruta HDFS:** `/danper/silver/agroindustria`

| Campo | Tipo Spark | Descripción | Nulos |
|---|---|---|---:|
| `anio` | `bigint` | Año del registro | 0 |
| `archivo_origen` | `string` | Archivo original de procedencia | 0 |
| `cantidad_t` | `double` | Cantidad en toneladas | 0 |
| `cuadro_origen` | `bigint` | Numero de cuadro de la fuente original | 0 |
| `cultivo` | `string` | Nombre del cultivo | 0 |
| `hoja_origen` | `string` | Hoja del Excel original | 0 |
| `mes` | `string` | Mes de referencia | 0 |
| `numero_mes` | `bigint` | Número de mes | 0 |
| `presentacion` | `string` | Presentacion comercial del producto | 0 |
| `proceso` | `string` | Tipo de proceso agroindustrial reportado | 0 |

## Costos agrícolas

**Tabla:** `costos`

**Ruta HDFS:** `/danper/silver/costos`

| Campo | Tipo Spark | Descripción | Nulos |
|---|---|---|---:|
| `region` | `string` | Región de referencia | 0 |
| `tipo_costo` | `string` | Tipo de costo agricola registrado | 0 |
| `anio` | `int` | Año del registro | 0 |
| `numero_mes` | `int` | Número de mes | 0 |
| `mes` | `string` | Mes de referencia | 0 |
| `valor` | `double` | Valor numérico del indicador | 0 |
| `unidad` | `string` | Unidad de medida del valor | 0 |
| `archivo_origen` | `string` | Archivo original de procedencia | 0 |

## ENA 2025 - Producción

**Tabla:** `ena_produccion`

**Ruta HDFS:** `/danper/silver/ena_2025/produccion`

| Campo | Tipo Spark | Descripción | Nulos |
|---|---|---|---:|
| `ANIO` | `string` | Año de la encuesta ENA | 0 |
| `NSEGM` | `string` | Identificador del segmento de encuesta | 0 |
| `ID_PROD` | `string` | Identificador de productor en la encuesta | 0 |
| `UA` | `string` | Identificador de unidad agropecuaria | 0 |
| `NOMBREDD` | `string` | Departamento según ENA | 0 |
| `NOMBREPV` | `string` | Provincia según ENA | 0 |
| `NOMBREDI` | `string` | Distrito según ENA | 0 |
| `FACTOR_PRODUCTOR` | `string` | Factor de expansion del productor registrado en ENA; conservado como texto | 0 |
| `P105` | `string` | Numero de parcela o chacra que trabaja o conduce actualmente | 2 |
| `P105_DIB` | `string` | Identificador de parcela: 1 dibujada; 2 declarada; 3 declarada y dibujada | 2 |
| `P147` | `string` | Numero de parcela o chacra que trabajo o condujo en los ultimos 12 meses | 0 |
| `P203` | `string` | Numero de cultivo registrado en la parcela | 0 |
| `P204_NOM` | `string` | Nombre del cultivo cosechado según ENA | 0 |
| `P204_COD` | `string` | Codigo del cultivo cosechado segun ENA | 0 |
| `P205_N` | `string` | Numero de veces que se cosecho el cultivo | 0 |
| `P217_SUP_ha` | `double` | Superficie cosechada, hectáreas | 0 |
| `P219_EQUIV_KG` | `double` | Factor de equivalencia de la unidad declarada a kilogramos; interpretacion contrastada con los valores del CSV, no localizada textualmente en el diccionario ENA | 0 |
| `P220_1_VAL` | `double` | Valor de producción destinado a venta, soles | 1 |
| `P220_1_PRE_KG` | `double` | Precio por kilogramo asociado a la produccion destinada a venta; interpretacion contrastada con cantidades y valores del CSV | 1 |
| `P220_2_VAL` | `double` | Valor de producción destinado al hogar, soles | 46 |
| `P220_2_PRE_KG` | `double` | Precio por kilogramo asociado a la produccion destinada al consumo del hogar; interpretacion inferida de los campos y valores del CSV | 46 |
| `cultivo_normalizado` | `string` | Cultivo normalizado | 0 |
| `archivo_origen` | `string` | Archivo original de procedencia | 0 |
| `ruta_bronze` | `string` | Ruta del archivo original en HDFS Bronze | 0 |
| `fila_csv` | `int` | Número de fila del CSV original | 0 |

## ENA 2025 - Insumos

**Tabla:** `ena_insumos`

**Ruta HDFS:** `/danper/silver/ena_2025/insumos`

| Campo | Tipo Spark | Descripción | Nulos |
|---|---|---|---:|
| `ANIO` | `string` | Año de la encuesta ENA | 0 |
| `NSEGM` | `string` | Identificador del segmento de encuesta | 0 |
| `ID_PROD` | `string` | Identificador de productor en la encuesta | 0 |
| `UA` | `string` | Identificador de unidad agropecuaria | 0 |
| `NOMBREDD` | `string` | Departamento según ENA | 0 |
| `NOMBREPV` | `string` | Provincia según ENA | 0 |
| `NOMBREDI` | `string` | Distrito según ENA | 0 |
| `FACTOR_PRODUCTOR` | `string` | Factor de expansion del productor registrado en ENA; conservado como texto | 0 |
| `P234_N` | `string` | Identificador ordinal del cultivo en el modulo ENA | 0 |
| `P234_NOM` | `string` | Nombre del cultivo cosechado según ENA | 0 |
| `P234_COD` | `string` | Codigo del cultivo en el modulo ENA | 0 |
| `P235_VAL` | `double` | Gasto en semilla, soles | 23 |
| `P235_PRE_KG` | `double` | Precio de semilla por kilogramo | 23 |
| `P237_VAL` | `double` | Gasto en abono, soles | 8 |
| `P237_PRE_KG` | `double` | Precio del abono por kilogramo | 8 |
| `cultivo_normalizado` | `string` | Cultivo normalizado | 0 |
| `archivo_origen` | `string` | Archivo original de procedencia | 0 |
| `ruta_bronze` | `string` | Ruta del archivo original en HDFS Bronze | 0 |
| `fila_csv` | `int` | Número de fila del CSV original | 0 |

## ENA 2025 - Uso de tierra

**Tabla:** `ena_uso_tierra`

**Ruta HDFS:** `/danper/silver/ena_2025/uso_tierra`

| Campo | Tipo Spark | Descripción | Nulos |
|---|---|---|---:|
| `ANIO` | `string` | Año de la encuesta ENA | 0 |
| `NSEGM` | `string` | Identificador del segmento de encuesta | 0 |
| `ID_PROD` | `string` | Identificador de productor en la encuesta | 0 |
| `UA` | `string` | Identificador de unidad agropecuaria | 0 |
| `NOMBREDD` | `string` | Departamento según ENA | 0 |
| `NOMBREPV` | `string` | Provincia según ENA | 0 |
| `NOMBREDI` | `string` | Distrito según ENA | 0 |
| `FACTOR_SUPERFICIE` | `string` | Factor de expansion de superficie registrado en ENA; conservado como texto | 0 |
| `P105` | `string` | Numero de parcela o chacra que trabaja o conduce actualmente | 0 |
| `P105_DIB` | `string` | Identificador de parcela: 1 dibujada; 2 declarada; 3 declarada y dibujada | 0 |
| `P115_LOTE` | `string` | Numero de lote en la parcela dibujada | 17 |
| `P115` | `string` | Numero de cultivo o uso de la tierra | 0 |
| `P115_NOM` | `string` | Cultivo según módulo de uso de tierra | 0 |
| `P115_COD` | `string` | Codigo del cultivo en el modulo de uso de tierra | 0 |
| `P116_NOM` | `string` | Nombre de la variedad registrada | 0 |
| `P116_COD` | `string` | Codigo de variedad del cultivo | 0 |
| `P117_SUP_ha` | `double` | Superficie agrícola registrada, hectáreas | 0 |
| `cultivo_normalizado` | `string` | Cultivo normalizado | 0 |
| `archivo_origen` | `string` | Archivo original de procedencia | 0 |
| `ruta_bronze` | `string` | Ruta del archivo original en HDFS Bronze | 0 |
| `fila_csv` | `int` | Número de fila del CSV original | 0 |

## Indicadores de sostenibilidad Danper

**Tabla:** `sostenibilidad`

**Ruta HDFS:** `/danper/silver/sostenibilidad/danper_indicadores`

| Campo | Tipo Spark | Descripción | Nulos |
|---|---|---|---:|
| `anio_indicador` | `bigint` | Año al que corresponde el indicador | 0 |
| `anio_reporte` | `bigint` | Año del reporte que publica el indicador | 0 |
| `pagina_pdf` | `bigint` | Página física del PDF consultada | 0 |
| `indicador` | `string` | Nombre del indicador | 0 |
| `valor` | `double` | Valor numérico del indicador | 0 |
| `unidad` | `string` | Unidad de medida del valor | 0 |
| `alcance` | `string` | Ámbito al que corresponde el indicador | 0 |
| `archivo_origen` | `string` | Archivo original de procedencia | 0 |
| `ruta_bronze` | `string` | Ruta del archivo original en HDFS Bronze | 0 |
| `evidencia_textual` | `string` | Fragmento de evidencia localizado en el PDF | 0 |
| `metodo_extraccion` | `string` | Método empleado para extraer el indicador | 0 |
