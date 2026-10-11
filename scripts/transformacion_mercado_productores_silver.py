
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime
from collections import Counter
import argparse
import re
import subprocess
import time

from pyspark.sql import SparkSession
from pyspark.sql.types import (
    StructType, StructField, StringType,
    IntegerType, DoubleType, DateType
)


# ==========================================
# CONFIGURACION
# ==========================================

BRONZE = "/danper/bronze/abastecimiento/mercado_productores"
SILVER = "/danper/silver/mercado_productores"

ANIOS = (2024, 2025)
PDF_ESPERADOS = 24
REGISTROS_REFERENCIA = 756

CATEGORIAS = {
    "ACEITE COMESTIBLE",
    "ARROZ",
    "AZUCAR",
    "FIDEOS",
    "HARINA",
    "LECHE",
    "MENESTRAS"
}

SCHEMA = StructType([
    StructField("fecha_reporte", DateType(), False),
    StructField("anio", IntegerType(), False),
    StructField("mes_numero", IntegerType(), False),
    StructField("mercado", StringType(), False),
    StructField("categoria", StringType(), False),
    StructField("producto", StringType(), False),
    StructField("unidad_medida", StringType(), False),
    StructField("precio_7dias_soles", DoubleType(), False),
    StructField("precio_ayer_soles", DoubleType(), False),
    StructField("precio_hoy_soles", DoubleType(), False),
    StructField("variacion_porcentaje", DoubleType(), False),
    StructField("archivo_origen", StringType(), False),
    StructField("ruta_bronze", StringType(), False)
])


# ==========================================
# FECHA DEL REPORTE
# ==========================================

def obtener_fecha(nombre):
    coincidencia = re.search(
        r"(\d{2}-\d{2}-\d{4})\.pdf$",
        nombre,
        re.IGNORECASE
    )

    if not coincidencia:
        raise ValueError(
            f"Fecha no reconocida: {nombre}"
        )

    return datetime.strptime(
        coincidencia.group(1),
        "%d-%m-%Y"
    ).date()


# ==========================================
# EXTRAER TABLA PRINCIPAL DEL PDF
# ==========================================

def extraer_pdf(archivo, ruta_bronze):
    resultado = subprocess.run(
        ["pdftotext", "-layout", str(archivo), "-"],
        capture_output=True,
        text=True,
        check=True,
        timeout=20
    )

    lineas = resultado.stdout.splitlines()
    fecha = obtener_fecha(archivo.name)

    registros = []
    categoria_actual = None
    dentro_tabla = False
    tabla_detectada = False

    for linea in lineas:
        texto = linea.strip()

        # La tabla principal contiene los precios
        # actuales y la variacion porcentual.
        if (
            "Unidad de Medida" in texto
            and "Variación" in texto
        ):
            dentro_tabla = True
            tabla_detectada = True
            continue

        if not dentro_tabla:
            continue

        # No mezclar con la tabla historica
        # que aparece despues.
        if (
            "Sin información" in texto
            or "Los precios incluyen IGV" in texto
            or "Fuente:" in texto
            or "COMPORTAMIENTO DE LOS PRECIOS" in texto
        ):
            break

        if texto in CATEGORIAS:
            categoria_actual = texto
            continue

        # Separar columnas por dos o mas espacios.
        # Evita expresiones regulares lentas.
        columnas = re.split(
            r"\s{2,}",
            texto
        )

        if len(columnas) != 6:
            continue

        if not columnas[5].endswith("%"):
            continue

        try:
            precio_7dias = float(columnas[2])
            precio_ayer = float(columnas[3])
            precio_hoy = float(columnas[4])
            variacion = float(
                columnas[5].replace("%", "")
            )
        except ValueError:
            continue

        if categoria_actual is None:
            raise ValueError(
                "Producto sin categoria en "
                f"{archivo.name}: {texto}"
            )

        producto = columnas[0].strip()
        unidad = columnas[1].strip()

        registros.append((
            fecha,
            fecha.year,
            fecha.month,
            "MERCADO_PRODUCTORES_SANTA_ANITA",
            categoria_actual,
            producto,
            unidad,
            precio_7dias,
            precio_ayer,
            precio_hoy,
            variacion,
            archivo.name,
            ruta_bronze
        ))

    if not tabla_detectada:
        raise ValueError(
            "No se encontro la tabla principal: "
            f"{archivo.name}"
        )

    if not registros:
        raise ValueError(
            "No se extrajeron productos: "
            f"{archivo.name}"
        )

    return registros


# ==========================================
# DESCARGAR ARCHIVOS DESDE BRONZE
# ==========================================

def descargar_pdf(directorio):
    archivos = []

    for anio in ANIOS:
        destino = Path(directorio) / str(anio)
        destino.mkdir(
            parents=True,
            exist_ok=True
        )

        ruta = f"{BRONZE}/{anio}/*.pdf"

        print(
            f"Recuperando Bronze {anio}...",
            flush=True
        )

        subprocess.run(
            [
                "hdfs", "dfs", "-get",
                ruta,
                str(destino)
            ],
            check=True
        )

        encontrados = sorted(
            destino.glob("*.pdf")
        )

        print(
            f"PDF recuperados {anio}: "
            f"{len(encontrados)}",
            flush=True
        )

        if len(encontrados) != 12:
            raise ValueError(
                f"Cantidad inesperada de PDF "
                f"para {anio}: {len(encontrados)}"
            )

        for archivo in encontrados:
            archivos.append((
                archivo,
                f"{BRONZE}/{anio}/{archivo.name}"
            ))

    if len(archivos) != PDF_ESPERADOS:
        raise ValueError(
            f"Se esperaban {PDF_ESPERADOS} PDF, "
            f"pero se encontraron {len(archivos)}."
        )

    return archivos


# ==========================================
# CONTROLES DE CALIDAD
# ==========================================

def validar_registros(registros, archivos):
    total = len(registros)

    claves = [
        (
            fila[0],
            fila[4],
            fila[5],
            fila[6]
        )
        for fila in registros
    ]

    duplicados = (
        len(claves) - len(set(claves))
    )

    precios_invalidos = sum(
        any(
            precio < 0
            for precio in fila[7:10]
        )
        for fila in registros
    )

    categorias = Counter(
        fila[4]
        for fila in registros
    )

    periodos = {
        (fila[1], fila[2])
        for fila in registros
    }

    archivos_con_datos = {
        fila[11]
        for fila in registros
    }

    # Revisar diferencias por redondeo entre
    # variacion publicada y variacion calculada.
    diferencias_variacion = 0

    for fila in registros:
        precio_ayer = fila[8]
        precio_hoy = fila[9]
        variacion_publicada = fila[10]

        if precio_ayer > 0:
            variacion_calculada = (
                (precio_hoy - precio_ayer)
                / precio_ayer * 100
            )

            if abs(
                variacion_calculada -
                variacion_publicada
            ) > 0.15:
                diferencias_variacion += 1

    print("\n===== CALIDAD SILVER =====")
    print("PDF procesados:", len(archivos))
    print("Registros:", total)
    print("Duplicados:", duplicados)
    print("Precios negativos:", precios_invalidos)
    print("Categorias:", len(categorias))
    print("Periodos distintos:", len(periodos))
    print("PDF con datos:", len(archivos_con_datos))
    print(
        "Variaciones a revisar:",
        diferencias_variacion
    )

    print("\n===== REGISTROS POR CATEGORIA =====")

    for categoria, cantidad in sorted(
        categorias.items()
    ):
        print(categoria, ":", cantidad)

    if duplicados > 0:
        raise ValueError(
            "Se detectaron registros duplicados."
        )

    if precios_invalidos > 0:
        raise ValueError(
            "Se encontraron precios negativos."
        )

    if len(archivos_con_datos) != PDF_ESPERADOS:
        raise ValueError(
            "Existen PDF sin datos extraidos."
        )

    if len(periodos) != 24:
        raise ValueError(
            "No se identificaron los 24 periodos."
        )

    if set(categorias) != CATEGORIAS:
        raise ValueError(
            "Las categorias identificadas "
            "no coinciden con las esperadas."
        )

    if total != REGISTROS_REFERENCIA:
        raise ValueError(
            "La cantidad de filas difiere "
            "de la validacion exploratoria: "
            f"{total} frente a "
            f"{REGISTROS_REFERENCIA}."
        )

    print("\nRESULTADO: VALIDACIONES SUPERADAS")


# ==========================================
# PROGRAMA PRINCIPAL
# ==========================================

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--ejecutar",
        action="store_true",
        help="Guardar datos en HDFS Silver"
    )

    args = parser.parse_args()
    inicio = time.time()

    print(
        "===== MERCADO PRODUCTORES SILVER =====",
        flush=True
    )

    if args.ejecutar:
        print(
            "Modo: TRANSFORMACION Y ESCRITURA",
            flush=True
        )
    else:
        print(
            "Modo: VALIDACION SIN ESCRITURA",
            flush=True
        )

    registros = []

    with TemporaryDirectory() as temporal:
        archivos = descargar_pdf(temporal)
        total_archivos = len(archivos)

        for i, (archivo, ruta_bronze) in enumerate(
            archivos, 1
        ):
            print(
                f"\n[{i}/{total_archivos}] "
                f"Procesando: {archivo.name}",
                flush=True
            )

            datos = extraer_pdf(
                archivo,
                ruta_bronze
            )

            registros.extend(datos)

            porcentaje = (
                i / total_archivos * 100
            )

            print(
                f"Filas extraidas: {len(datos)} "
                f"| Acumuladas: {len(registros)} "
                f"| PROGRESO: {porcentaje:.0f}%",
                flush=True
            )

    validar_registros(
        registros,
        archivos
    )

    spark = (
        SparkSession.builder
        .appName(
            "Danper_Mercado_Productores_Silver"
        )
        .master("local[2]")
        .getOrCreate()
    )

    try:
        spark.sparkContext.setLogLevel(
            "ERROR"
        )

        rdd = spark.sparkContext.parallelize(
            registros,
            2
        )

        df = spark.createDataFrame(
            rdd,
            schema=SCHEMA
        )

        print("\n===== RESULTADOS SPARK =====")
        print(
            "Registros estructurados:",
            df.count()
        )

        print("\n===== DATOS POR ANIO =====")

        df.groupBy("anio").count().orderBy(
            "anio"
        ).show()

        print("\n===== MUESTRA =====")

        df.select(
            "fecha_reporte",
            "categoria",
            "producto",
            "unidad_medida",
            "precio_hoy_soles",
            "variacion_porcentaje"
        ).show(10, truncate=False)

        if not args.ejecutar:
            print(
                "\nValidacion completada."
            )
            print(
                "No se modifico HDFS Silver."
            )
            return

        print("\n===== ESCRIBIENDO SILVER =====")

        df.write.mode(
            "overwrite"
        ).parquet(SILVER)

        print("Silver generado:", SILVER)
        print(
            "Registros guardados:",
            df.count()
        )

    finally:
        spark.stop()

        print(
            "\nTiempo total:",
            round(
                time.time() - inicio,
                2
            ),
            "segundos"
        )


if __name__ == "__main__":
    main()
