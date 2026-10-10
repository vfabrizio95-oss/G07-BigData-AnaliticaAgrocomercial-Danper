from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime
import subprocess
import re
import unicodedata

from pyspark.sql import SparkSession
from pyspark.sql.types import (
    StructType, StructField,
    StringType, DoubleType
)

BRONZE = "/danper/bronze/abastecimiento"
SILVER = "/danper/silver/abastecimiento"
CALIDAD = "/danper/calidad/abastecimiento/incidencias"

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
    StructField("archivo_origen", StringType(), False),
])

SCHEMA_CALIDAD = StructType([
    StructField("fecha_reporte", StringType(), False),
    StructField("producto", StringType(), False),
    StructField("campo", StringType(), False),
    StructField("valor_origen", StringType(), False),
    StructField("tipo_incidencia", StringType(), False),
    StructField("archivo_origen", StringType(), False),
])


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
        raise ValueError(f"Fecha no reconocida: {nombre}")

    return datetime.strptime(
        coincidencia.group(0)[:10],
        "%d-%m-%Y"
    ).date().isoformat()


def extraer_pdf(archivo):
    proceso = subprocess.run(
        ["pdftotext", "-layout", str(archivo), "-"],
        capture_output=True,
        text=True,
        check=True
    )

    lineas = proceso.stdout.splitlines()
    fecha = fecha_desde_nombre(archivo.name)

    registros = []
    incidencias = []

    # Separa el nombre del producto, ingresos,
    # unidad comercial y precios.
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

    for indice, linea in enumerate(lineas):
        coincidencia = patron.match(linea)

        if not coincidencia:
            continue

        producto = normalizar(coincidencia.group(1))
        campos_ingreso = coincidencia.group(2).split()

        if len(campos_ingreso) != 4:
            raise ValueError(
                f"Columnas de ingreso inesperadas: {linea}"
            )

        unidad = normalizar(coincidencia.group(3))
        equivalencia = float(coincidencia.group(4))
        precio_ayer = float(coincidencia.group(5))
        precio_hoy = float(coincidencia.group(6))
        resto = coincidencia.group(7).strip()

        ingresos = []

        nombres_ingreso = [
            "ingreso_ayer_t",
            "ingreso_hoy_t",
            "promedio_ingreso_7dias_t",
            "promedio_ingreso_4semanas_t"
        ]

        for campo, original in zip(
            nombres_ingreso, campos_ingreso
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

        # Enero tiene el precio de 7 días
        # en la misma línea del producto.
        if re.fullmatch(r"\d+(?:\.\d+)?", resto):
            precio_7dias = float(resto)

        else:
            # Diciembre incluye tendencia y el precio
            # de siete días en la línea siguiente.
            if resto:
                tendencia = normalizar(resto)

            for siguiente in lineas[indice + 1:indice + 4]:
                contenido = siguiente.strip()

                if not contenido:
                    continue

                if re.fullmatch(
                    r"\d+(?:\.\d+)?", contenido
                ):
                    precio_7dias = float(contenido)

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


def main():
    spark = (
        SparkSession.builder
        .appName("Danper_Abastecimiento_Silver")
        .master("local[2]")
        .getOrCreate()
    )

    try:
        with TemporaryDirectory() as temporal:
            subprocess.run(
                [
                    "hdfs", "dfs", "-get",
                    f"{BRONZE}/*.pdf",
                    temporal
                ],
                check=True
            )

            archivos = sorted(
                Path(temporal).glob("*.pdf")
            )

            if len(archivos) != 2:
                raise ValueError(
                    f"Se esperaban 2 PDF; hay {len(archivos)}"
                )

            registros = []
            incidencias = []

            for archivo in archivos:
                datos, problemas = extraer_pdf(archivo)
                registros.extend(datos)
                incidencias.extend(problemas)

        print("===== EXTRACCION ABASTECIMIENTO =====")
        print("PDF procesados:", len(archivos))
        print("Registros:", len(registros))
        print("Incidencias:", len(incidencias))

        if len(registros) != 4:
            raise ValueError(
                "Se esperaban 4 registros producto-fecha"
            )

        df = spark.createDataFrame(
            registros, SCHEMA
        )

        df_calidad = spark.createDataFrame(
            incidencias, SCHEMA_CALIDAD
        )

        duplicados = (
            df.count()
            - df.select(
                "fecha_reporte", "producto"
            ).distinct().count()
        )

        print("\n===== CALIDAD =====")
        print("Duplicados:", duplicados)

        if duplicados:
            raise ValueError(
                "Existen registros producto-fecha duplicados"
            )

        # Mostrar resultados antes de almacenarlos.
        df.select(
            "fecha_reporte",
            "producto",
            "ingreso_hoy_t",
            "precio_hoy_soles",
            "unidad_medida",
            "precio_7dias_soles"
        ).orderBy(
            "fecha_reporte", "producto"
        ).show(truncate=False)

        # Guardar Silver y las incidencias.
        df.write.mode("overwrite").parquet(SILVER)

        df_calidad.write.mode("overwrite").parquet(
            CALIDAD
        )

        print("\n===== RESULTADO =====")
        print("Silver:", SILVER)
        print("Registros guardados:", df.count())
        print("Incidencias guardadas:", df_calidad.count())

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
