
from pathlib import Path
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

SALIDA = Path("docs/silver")

TABLAS = {
    "produccion": ("/danper/silver/produccion", "Producción agrícola regional"),
    "exportaciones_danper": ("/danper/silver/exportaciones/danper", "Exportaciones de Danper"),
    "exportaciones_regionales": ("/danper/silver/exportaciones/regionales", "Exportaciones regionales"),
    "abastecimiento": ("/danper/silver/abastecimiento", "Abastecimiento GMML"),
    "mercado_productores": ("/danper/silver/mercado_productores", "Mercado de Productores"),
    "agroindustria": ("/danper/silver/agroindustria", "Agroindustria"),
    "costos": ("/danper/silver/costos", "Costos agrícolas"),
    "ena_produccion": ("/danper/silver/ena_2025/produccion", "ENA 2025 - Producción"),
    "ena_insumos": ("/danper/silver/ena_2025/insumos", "ENA 2025 - Insumos"),
    "ena_uso_tierra": ("/danper/silver/ena_2025/uso_tierra", "ENA 2025 - Uso de tierra"),
    "sostenibilidad": (
        "/danper/silver/sostenibilidad/danper_indicadores",
        "Indicadores de sostenibilidad Danper"
    )
}

DESCRIPCIONES = {
    'ANIO': 'Año de la encuesta ENA',
    'FACTOR_PRODUCTOR': 'Factor de expansion del productor registrado en ENA; conservado como texto',
    'FACTOR_SUPERFICIE': 'Factor de expansion de superficie registrado en ENA; conservado como texto',
    'ID_PROD': 'Identificador de productor en la encuesta',
    'NOMBREDD': 'Departamento según ENA',
    'NOMBREDI': 'Distrito según ENA',
    'NOMBREPV': 'Provincia según ENA',
    'NSEGM': 'Identificador del segmento de encuesta',
    'P105': 'Numero de parcela o chacra que trabaja o conduce actualmente',
    'P105_DIB': 'Identificador de parcela: 1 dibujada; 2 declarada; 3 declarada y dibujada',
    'P115': 'Numero de cultivo o uso de la tierra',
    'P115_COD': 'Codigo del cultivo en el modulo de uso de tierra',
    'P115_LOTE': 'Numero de lote en la parcela dibujada',
    'P115_NOM': 'Cultivo según módulo de uso de tierra',
    'P116_COD': 'Codigo de variedad del cultivo',
    'P116_NOM': 'Nombre de la variedad registrada',
    'P117_SUP_ha': 'Superficie agrícola registrada, hectáreas',
    'P147': 'Numero de parcela o chacra que trabajo o condujo en los ultimos 12 meses',
    'P203': 'Numero de cultivo registrado en la parcela',
    'P204_COD': 'Codigo del cultivo cosechado segun ENA',
    'P204_NOM': 'Nombre del cultivo cosechado según ENA',
    'P205_N': 'Numero de veces que se cosecho el cultivo',
    'P217_SUP_ha': 'Superficie cosechada, hectáreas',
    'P219_EQUIV_KG': 'Factor de equivalencia de la unidad declarada a kilogramos; interpretacion contrastada con los valores del CSV, no localizada textualmente en el diccionario ENA',
    'P220_1_PRE_KG': 'Precio por kilogramo asociado a la produccion destinada a venta; interpretacion contrastada con cantidades y valores del CSV',
    'P220_1_VAL': 'Valor de producción destinado a venta, soles',
    'P220_2_PRE_KG': 'Precio por kilogramo asociado a la produccion destinada al consumo del hogar; interpretacion inferida de los campos y valores del CSV',
    'P220_2_VAL': 'Valor de producción destinado al hogar, soles',
    'P234_COD': 'Codigo del cultivo en el modulo ENA',
    'P234_N': 'Identificador ordinal del cultivo en el modulo ENA',
    'P234_NOM': 'Nombre del cultivo cosechado según ENA',
    'P235_PRE_KG': 'Precio de semilla por kilogramo',
    'P235_VAL': 'Gasto en semilla, soles',
    'P237_PRE_KG': 'Precio del abono por kilogramo',
    'P237_VAL': 'Gasto en abono, soles',
    'UA': 'Identificador de unidad agropecuaria',
    'aduana': 'Dependencia aduanera registrada',
    'agente': 'Agente registrado en la operacion aduanera',
    'alcance': 'Ámbito al que corresponde el indicador',
    'anio': 'Año del registro',
    'anio_indicador': 'Año al que corresponde el indicador',
    'anio_reporte': 'Año del reporte que publica el indicador',
    'archivo_origen': 'Archivo original de procedencia',
    'cantidad_t': 'Cantidad en toneladas',
    'categoria': 'Categoria comercial del producto',
    'codigo_cultivo': 'Código del cultivo en la fuente',
    'columna_origen': 'Columna de origen',
    'cuadro_origen': 'Numero de cuadro de la fuente original',
    'cultivo': 'Nombre del cultivo',
    'cultivo_normalizado': 'Cultivo normalizado',
    'distrito': 'Distrito de referencia',
    'equivalencia_kg': 'Equivalencia de la unidad comercial en kilogramos',
    'evidencia_textual': 'Fragmento de evidencia localizado en el PDF',
    'exportador': 'Nombre o razon social del exportador',
    'fecha_reporte': 'Fecha del reporte',
    'fila_csv': 'Número de fila del CSV original',
    'fila_excel': 'Número de fila de Excel de origen',
    'fob_usd': 'Valor FOB en dólares estadounidenses',
    'hoja_origen': 'Hoja del Excel original',
    'indicador': 'Nombre del indicador',
    'ingreso_ayer_t': 'Ingreso reportado del dia anterior, toneladas',
    'ingreso_hoy_t': 'Ingreso reportado del dia actual, toneladas',
    'mercado': 'Nombre del mercado mayorista de origen',
    'mes': 'Mes de referencia',
    'mes_numero': 'Número de mes',
    'mes_origen': 'Mes indicado en la fuente original',
    'metodo_extraccion': 'Método empleado para extraer el indicador',
    'numero_mes': 'Número de mes',
    'pagina_origen': 'Página de origen disponible en la fuente',
    'pagina_pdf': 'Página física del PDF consultada',
    'pais': 'Pais registrado en la operacion de exportacion',
    'periodo': 'Período de referencia',
    'posicion_mensual': 'Posición del mes en el archivo original',
    'precio_7dias_soles': 'Precio de referencia de siete días, en soles',
    'precio_ayer_soles': 'Precio reportado para el día anterior, en soles',
    'precio_hoy_soles': 'Precio reportado para el día actual, en soles',
    'presentacion': 'Presentacion comercial del producto',
    'proceso': 'Tipo de proceso agroindustrial reportado',
    'producto': 'Nombre del producto reportado',
    'promedio_ingreso_4semanas_t': 'Promedio de ingreso de cuatro semanas, toneladas',
    'promedio_ingreso_7dias_t': 'Promedio de ingreso de siete dias, toneladas',
    'provincia': 'Provincia de referencia',
    'region': 'Región de referencia',
    'ruc': 'Registro Unico de Contribuyentes del exportador',
    'ruta_bronze': 'Ruta del archivo original en HDFS Bronze',
    'tendencia': 'Tendencia reportada en el documento original',
    'tipo_costo': 'Tipo de costo agricola registrado',
    'unidad': 'Unidad de medida del valor',
    'unidad_medida': 'Unidad de medida original',
    'valor': 'Valor numérico del indicador',
    'variable': 'Variable registrada en la fuente',
    'variacion_porcentaje': 'Variación porcentual reportada',
}

def guardar_nuevo(nombre, contenido):
    destino = SALIDA / nombre
    if destino.exists():
        raise FileExistsError(
            f"No se sobrescribira un documento existente: {destino}"
        )
    destino.write_text(contenido, encoding="utf-8")
    print("Documento creado:", destino, flush=True)

def main():
    SALIDA.mkdir(parents=True, exist_ok=True)

    for nombre in ("README.md", "diccionario_datos.md", "reporte_calidad.md"):
        if (SALIDA / nombre).exists():
            raise FileExistsError(
                f"Ya existe docs/silver/{nombre}; no se modifico nada"
            )

    spark = (
        SparkSession.builder
        .appName("Documentacion_Danper_Silver")
        .master("local[2]")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")

    resumen = []
    diccionario = [
        "# Diccionario de datos - Capa Silver",
        "",
        "Generado a partir de los esquemas reales almacenados en HDFS.",
        "Las descripciones no confirmadas se indican como pendientes.",
        ""
    ]
    calidad = [
        "# Reporte de calidad - Capa Silver",
        "",
        "## Alcance",
        "",
        "Auditoría de 11 tablas mediante PySpark.",
        "Los controles no reemplazan la validación semántica de negocio.",
        ""
    ]

    try:
        for i, (nombre, (ruta, descripcion)) in enumerate(TABLAS.items(), 1):
            print(f"[{i}/11] Documentando {nombre}", flush=True)

            df = spark.read.parquet(ruta)
            total = df.count()
            duplicados = total - df.distinct().count()

            expresiones = [
                F.sum(
                    F.when(F.col(c).isNull(), 1).otherwise(0)
                ).alias(c)
                for c in df.columns
            ]
            nulos = df.agg(*expresiones).first().asDict()

            resumen.append((nombre, descripcion, ruta, total))

            diccionario.extend([
                f"## {descripcion}",
                "",
                f"**Tabla:** `{nombre}`",
                "",
                f"**Ruta HDFS:** `{ruta}`",
                "",
                "| Campo | Tipo Spark | Descripción | Nulos |",
                "|---|---|---|---:|"
            ])

            for campo in df.schema.fields:
                descripcion_campo = DESCRIPCIONES.get(
                    campo.name, "Definición pendiente de confirmar"
                )
                diccionario.append(
                    f"| `{campo.name}` | "
                    f"`{campo.dataType.simpleString()}` | "
                    f"{descripcion_campo} | "
                    f"{nulos[campo.name]} |"
                )

            diccionario.append("")

            completos_nulos = [
                c for c, cantidad in nulos.items()
                if cantidad == total
            ]

            parciales = [
                f"`{c}`: {cantidad}"
                for c, cantidad in nulos.items()
                if 0 < cantidad < total
            ]

            calidad.extend([
                f"## {nombre}",
                "",
                f"- Registros: **{total}**",
                f"- Columnas: **{len(df.columns)}**",
                f"- Duplicados exactos: **{duplicados}**",
                "- Columnas totalmente nulas: "
                + (", ".join(completos_nulos) or "Ninguna"),
                "- Valores nulos parciales: "
                + (", ".join(parciales) or "Ninguno"),
                ""
            ])

            print(f"PROGRESO: {i / 11 * 100:.0f}%", flush=True)

    finally:
        spark.stop()

    total_filas = sum(fila[3] for fila in resumen)

    readme = [
        "# Procesamiento Silver - Proyecto Danper",
        "",
        "## Objetivo",
        "",
        "Transformar datos de HDFS Bronze en conjuntos Parquet "
        "estructurados, trazables y utilizables por la capa Gold.",
        "",
        "## Arquitectura",
        "",
        "`HDFS Bronze -> Python/PySpark -> HDFS Silver -> Gold`",
        "",
        "La solución se ejecuta en infraestructura local (on-premise).",
        "",
        "## Tablas procesadas",
        "",
        "| Tabla | Descripción | Registros | Ruta Silver |",
        "|---|---|---:|---|"
    ]

    for nombre, descripcion, ruta, cantidad in resumen:
        readme.append(
            f"| `{nombre}` | {descripcion} | "
            f"{cantidad:,} | `{ruta}` |"
        )

    readme.extend([
        "",
        f"**Total:** {len(resumen)} tablas y {total_filas:,} filas.",
        "",
        "El total representa filas de distintas fuentes y "
        "granularidades; no debe interpretarse como productores únicos.",
        "",
        "## Scripts",
        "",
        "Los procesos de transformación están en `scripts/`.",
        "Algunos utilizan modo de validación antes de escribir en HDFS.",
        "Revisar las opciones de cada script antes de ejecutarlo nuevamente.",
        "",
        "## Documentos complementarios",
        "",
        "- `diccionario_datos.md`: campos y tipos Spark.",
        "- `reporte_calidad.md`: controles y valores ausentes.",
        "",
        "## Precauciones",
        "",
        "- No sobrescribir Parquet sin realizar un respaldo.",
        "- ENA 2025 es información muestral, no operaciones internas de Danper.",
        "- Los indicadores ambientales tienen diferentes años y alcances.",
        "- Algunos datos originales carecen de valores o metadatos.",
        ""
    ])

    calidad.extend([
        "## Controles numéricos",
        "",
        "En el Paso 82 se comprobaron valores negativos en "
        "campos no negativos, NaN e infinitos en columnas numéricas.",
        "**Resultado observado: 0 incidencias numéricas.**",
        "",
        "## Limitaciones conocidas",
        "",
        "- Exportaciones Danper: 138 registros de 2026 "
        "sin `pagina_origen`.",
        "- Abastecimiento: indicadores no disponibles "
        "en parte de los reportes originales.",
        "- ENA insumos: `P235_VAL` y `P235_PRE_KG` "
        "sin valores disponibles en la selección.",
        "- ENA usa factores de expansión que requieren "
        "tratamiento metodológico antes de estimaciones poblacionales.",
        "- La ausencia de duplicados exactos no garantiza "
        "ausencia de duplicados según claves de negocio.",
        "- Sostenibilidad: conservar año del indicador, "
        "año del reporte, página y alcance.",
        ""
    ])

    guardar_nuevo("README.md", "\n".join(readme) + "\n")
    guardar_nuevo(
        "diccionario_datos.md", "\n".join(diccionario) + "\n"
    )
    guardar_nuevo(
        "reporte_calidad.md", "\n".join(calidad) + "\n"
    )

    print("\nDOCUMENTACION GENERADA CORRECTAMENTE", flush=True)
    print("Tablas:", len(resumen), flush=True)
    print("Filas:", total_filas, flush=True)

if __name__ == "__main__":
    main()
