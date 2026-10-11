from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime
from collections import Counter
import argparse
import subprocess
import re
import unicodedata

from pyspark.sql import SparkSession
from pyspark.sql.types import (
    StructType, StructField,
    StringType, DoubleType
)


# ==========================================
# CONFIGURACION
# ==========================================

BRONZE = "/danper/bronze/abastecimiento"
SILVER = "/danper/silver/abastecimiento"
CALIDAD = "/danper/calidad/abastecimiento/incidencias"

FUENTES_GMML = [
    f"{BRONZE}/gmml_2024/*.pdf",
    f"{BRONZE}/gmml_2025/*.pdf",
    f"{BRONZE}/gmml_2026/*.pdf",
    f"{BRONZE}/*.pdf"
]

PDF_ESPERADOS = 33
PRODUCTOS_ESPERADOS = {"ALCACHOFA", "ESPARRAGO"}


# ==========================================
# ESQUEMAS
# ==========================================

SCHEMA = StructType([
    StructField("fecha_reporte", StringType(), False),
    StructField("mercado", StringType(), False),
    StructField("producto", StringType(), False),
    StructField("ingreso_ayer_t", DoubleType(), True),
    StructField("ingreso_hoy_t", DoubleType(), True),
    StructField("promedio_ingreso_7dias_t", DoubleType(), True),
    StructField("promedio_ingreso_4semanas_t", DoubleType(), True),
    StructField("unidad_medida", StringType(), False),
    StructField("equivalencia_kg", DoubleType(), False),
    StructField("precio_ayer_soles", DoubleType(), False),
    StructField("precio_hoy_soles", DoubleType(), False),
    StructField("precio_7dias_soles", DoubleType(), True),
    StructField("tendencia", StringType(), True),
    StructField("archivo_origen", StringType(), False)
])

SCHEMA_CALIDAD = StructType([
    StructField("fecha_reporte", StringType(), False),
    StructField("producto", StringType(), False),
    StructField("campo", StringType(), False),
    StructField("valor_origen", StringType(), False),
    StructField("tipo_incidencia", StringType(), False),
    StructField("archivo_origen", StringType(), False)
])


# ==========================================
# FUNCIONES DEL EXTRACTOR ORIGINAL
# ==========================================

def normalizar(texto):
    texto = str(texto).strip().upper()

    return "".join(
        caracter
        for caracter in unicodedata.normalize("NFD", texto)
        if unicodedata.category(caracter) != "Mn"
    )


def convertir_numero(valor):
    if valor in (":", "-", "--", ""):
        return None

    return float(valor)


def fecha_desde_nombre(nombre):
    coincidencia = re.search(
        r"(\d{2})-(\d{2})-(\d{4})\.pdf$",
        nombre,
        re.IGNORECASE
    )

    if not coincidencia:
        raise ValueError(
            f"Fecha no reconocida: {nombre}"
        )

    return datetime.strptime(
        coincidencia.group(0)[:10],
        "%d-%m-%Y"
    ).date().isoformat()


def extraer_pdf(archivo):
    proceso = subprocess.run(
        [
            "pdftotext",
            "-layout",
            str(archivo),
            "-"
        ],
        capture_output=True,
        text=True,
        check=True
    )

    lineas = proceso.stdout.splitlines()
    fecha = fecha_desde_nombre(archivo.name)

    registros = []
    incidencias = []

    patron = re.compile(
        r"^\s*(Alcachofa|Esparrago|Espárrago)\s+"
        r"(.+?)\s+"
        r"(Docena|Paquete)\s+"
        r"(\d+(?:\.\d+)?)\s+"
        r"(\d+(?:\.\d+)?)\s+"
        r"(\d+(?:\.\d+)?)"
        r"(.*)$",
        re.IGNORECASE
    )

    nombres_ingreso = [
        "ingreso_ayer_t",
        "ingreso_hoy_t",
        "promedio_ingreso_7dias_t",
        "promedio_ingreso_4semanas_t"
    ]

    for indice, linea in enumerate(lineas):
        coincidencia = patron.match(linea)

        if not coincidencia:
            continue

        producto = normalizar(
            coincidencia.group(1)
        )

        campos_ingreso = (
            coincidencia.group(2).split()
        )

        if len(campos_ingreso) != 4:
            raise ValueError(
                f"Columnas inesperadas en "
                f"{archivo.name}: {linea}"
            )

        unidad = normalizar(
            coincidencia.group(3)
        )

        equivalencia = float(
            coincidencia.group(4)
        )

        precio_ayer = float(
            coincidencia.group(5)
        )

        precio_hoy = float(
            coincidencia.group(6)
        )

        resto = coincidencia.group(7).strip()

        ingresos = []

        for campo, original in zip(
            nombres_ingreso,
            campos_ingreso
        ):
            valor = convertir_numero(original)
            ingresos.append(valor)

            if valor is None:
                incidencias.append((
                    fecha,
                    producto,
                    campo,
                    original,
                    "VALOR_NO_DISPONIBLE",
                    archivo.name
                ))

        precio_7dias = None
        tendencia = None

        if re.fullmatch(
            r"\d+(?:\.\d+)?",
            resto
        ):
            precio_7dias = float(resto)

        else:
            if resto:
                tendencia = normalizar(resto)

            for siguiente in lineas[
                indice + 1:indice + 4
            ]:
                contenido = siguiente.strip()

                if not contenido:
                    continue

                if re.fullmatch(
                    r"\d+(?:\.\d+)?",
                    contenido
                ):
                    precio_7dias = float(
                        contenido
                    )

                break

        if precio_7dias is None:
            incidencias.append((
                fecha,
                producto,
                "precio_7dias_soles",
                resto,
                "EXTRACCION_NO_CONFIRMADA",
                archivo.name
            ))

        registros.append((
            fecha,
            "GMML_LIMA",
            producto,
            ingresos[0],
            ingresos[1],
            ingresos[2],
            ingresos[3],
            unidad,
            equivalencia,
            precio_ayer,
            precio_hoy,
            precio_7dias,
            tendencia,
            archivo.name
        ))

    return registros, incidencias


# ==========================================
# DESCARGAR PDF DESDE HDFS BRONZE
# ==========================================

def descargar_pdf_bronze(directorio):
    ruta_destino = Path(directorio)
    archivos_descargados = []

    for patron_hdfs in FUENTES_GMML:
        print(
            "Recuperando desde:",
            patron_hdfs
        )

        # Descargamos cada grupo por separado
        # para poder contar y verificar los PDF.
        antes = {
            p.name
            for p in ruta_destino.glob("*.pdf")
        }

        subprocess.run(
            [
                "hdfs", "dfs", "-get",
                patron_hdfs,
                str(ruta_destino)
            ],
            check=True
        )

        despues = {
            p.name
            for p in ruta_destino.glob("*.pdf")
        }

        nuevos = despues - antes

        print(
            "Archivos nuevos recuperados:",
            len(nuevos)
        )

        archivos_descargados.extend(
            sorted(nuevos)
        )

    archivos = sorted(
        ruta_destino.glob("*.pdf")
    )

    if len(archivos) != PDF_ESPERADOS:
        raise ValueError(
            f"Se esperaban {PDF_ESPERADOS} PDF GMML "
            f"y se encontraron {len(archivos)}. "
            "Revise las rutas o posibles nombres repetidos."
        )

    if len(archivos_descargados) != PDF_ESPERADOS:
        raise ValueError(
            "No se recuperaron 33 nombres de archivo "
            "distintos desde las fuentes configuradas."
        )

    return archivos


# ==========================================
# EXTRAER LOS 33 DOCUMENTOS
# ==========================================

def extraer_desde_bronze():
    registros = []
    incidencias = []

    with TemporaryDirectory() as temporal:
        archivos = descargar_pdf_bronze(
            temporal
        )

        print("\n===== EXTRACCION GMML =====")

        for archivo in archivos:
            datos, problemas = extraer_pdf(
                archivo
            )

            productos = {
                fila[2]
                for fila in datos
            }

            if (
                len(datos) != 2
                or productos != PRODUCTOS_ESPERADOS
            ):
                raise ValueError(
                    "Productos inesperados en: "
                    f"{archivo.name}. "
                    f"Registros: {len(datos)}, "
                    f"productos: {productos}"
                )

            registros.extend(datos)
            incidencias.extend(problemas)

            print(
                archivo.name[-14:],
                "| registros:", len(datos),
                "| incidencias:", len(problemas)
            )

    print("\nPDF procesados:", len(archivos))
    print("Registros extraidos:", len(registros))
    print("Incidencias:", len(incidencias))

    return archivos, registros, incidencias


# ==========================================
# VALIDAR CALIDAD
# ==========================================

def validar_datos(archivos, registros, incidencias):
    if len(archivos) != PDF_ESPERADOS:
        raise ValueError(
            "Cantidad incorrecta de reportes PDF."
        )

    if len(registros) != PDF_ESPERADOS * 2:
        raise ValueError(
            "Cantidad inesperada de registros."
        )

    claves = [
        (fila[0], fila[1], fila[2])
        for fila in registros
    ]

    duplicados = len(claves) - len(
        set(claves)
    )

    precios_nulos = sum(
        fila[10] is None
        for fila in registros
    )

    precios_negativos = sum(
        fila[10] is not None
        and fila[10] < 0
        for fila in registros
    )

    precios_siete_dias_nulos = sum(
        fila[11] is None
        for fila in registros
    )

    incidencias_por_tipo = Counter(
        fila[4]
        for fila in incidencias
    )

    print("\n===== CALIDAD GMML =====")
    print("Duplicados:", duplicados)
    print("Precios hoy nulos:", precios_nulos)
    print("Precios hoy negativos:", precios_negativos)
    print(
        "Precios 7 dias nulos:",
        precios_siete_dias_nulos
    )

    print("\n===== INCIDENCIAS =====")

    for tipo, cantidad in sorted(
        incidencias_por_tipo.items()
    ):
        print(tipo, ":", cantidad)

    extracciones_no_confirmadas = (
        incidencias_por_tipo.get(
            "EXTRACCION_NO_CONFIRMADA",
            0
        )
    )

    if duplicados:
        raise ValueError(
            "Existen registros duplicados."
        )

    if precios_nulos or precios_negativos:
        raise ValueError(
            "Existen precios actuales invalidos."
        )

    if extracciones_no_confirmadas:
        raise ValueError(
            "Hay extracciones de precios sin confirmar."
        )

    print("\nRESULTADO: VALIDACIONES SUPERADAS")


# ==========================================
# CREAR SESION SPARK
# ==========================================

def crear_spark():
    spark = (
        SparkSession.builder
        .appName(
            "Danper_Abastecimiento_GMML_Silver"
        )
        .master("local[2]")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel(
        "ERROR"
    )

    return spark


# ==========================================
# PROGRAMA PRINCIPAL
# ==========================================

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Transformacion GMML PDF a Silver"
        )
    )

    parser.add_argument(
        "--ejecutar",
        action="store_true",
        help=(
            "Guardar resultados e incidencias "
            "en HDFS"
        )
    )

    args = parser.parse_args()

    print(
        "===== ABASTECIMIENTO GMML SILVER ====="
    )

    if args.ejecutar:
        print(
            "Modo: TRANSFORMACION Y ESCRITURA"
        )
    else:
        print(
            "Modo: VALIDACION SIN ESCRITURA"
        )

    archivos, registros, incidencias = (
        extraer_desde_bronze()
    )

    validar_datos(
        archivos,
        registros,
        incidencias
    )

    spark = crear_spark()

    try:
        df = spark.createDataFrame(
            registros,
            schema=SCHEMA
        )

        df_calidad = spark.createDataFrame(
            incidencias,
            schema=SCHEMA_CALIDAD
        )

        print("\n===== RESULTADO SPARK =====")

        print(
            "Registros estructurados:",
            df.count()
        )

        print(
            "Incidencias estructuradas:",
            df_calidad.count()
        )

        print("\n===== REGISTROS POR ANIO =====")

        df.selectExpr(
            "substring(fecha_reporte, 1, 4) "
            "as anio"
        ).groupBy("anio").count().orderBy(
            "anio"
        ).show()

        print("\n===== MUESTRA DE DATOS =====")

        df.select(
            "fecha_reporte",
            "producto",
            "ingreso_hoy_t",
            "precio_hoy_soles",
            "unidad_medida",
            "precio_7dias_soles"
        ).orderBy(
            "fecha_reporte",
            "producto"
        ).show(10, truncate=False)

        if not args.ejecutar:
            print(
                "\nValidacion completada."
            )

            print(
                "No se modifico HDFS Silver "
                "ni la tabla de incidencias."
            )

            return

        print("\n===== ESCRIBIENDO EN HDFS =====")

        df.write.mode(
            "overwrite"
        ).parquet(SILVER)

        df_calidad.write.mode(
            "overwrite"
        ).parquet(CALIDAD)

        print("\n===== RESULTADO FINAL =====")
        print("Silver:", SILVER)

        print(
            "Registros guardados:",
            df.count()
        )

        print("Calidad:", CALIDAD)

        print(
            "Incidencias guardadas:",
            df_calidad.count()
        )

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
