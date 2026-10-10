from pathlib import Path
import pandas as pd

RUTA_DATOS = Path.home() / "proyecto_danper/datasets/exportaciones"

MESES = [
    "ENE", "FEB", "MAR", "ABR", "MAY", "JUN",
    "JUL", "AGO", "SET", "OCT", "NOV", "DIC"
]

# Orden de indicadores verificado en los Excel originales.
CONFIGURACION = {
    "ESPARRAGO": ["VALOR_FOB", "VOLUMEN", "PRECIO_FOB"],
    "ALCACHOFA": ["VOLUMEN", "VALOR_FOB", "PRECIO_FOB"],
    "ARANDANO": ["VOLUMEN", "VALOR_FOB", "PRECIO_FOB"],
    "PALTA": ["VALOR_FOB", "VOLUMEN", "PRECIO_FOB"],
    "UVA": ["VALOR_FOB", "VOLUMEN", "PRECIO_FOB"],
}

UNIDADES = {
    "VALOR_FOB": "MILES_USD",
    "VOLUMEN": "TONELADAS",
    "PRECIO_FOB": "USD_KG",
}


def identificar_cultivo(nombre):
    nombre = nombre.upper()

    if "PALTO" in nombre or "PALTA" in nombre:
        return "PALTA"

    for cultivo in CONFIGURACION:
        if cultivo in nombre:
            return cultivo

    return None


def convertir_numero(valor):
    if pd.isna(valor):
        return None

    try:
        return float(valor)
    except (ValueError, TypeError):
        return None


def extraer_exportaciones_regionales(ruta=None):
    ruta = Path(ruta) if ruta is not None else RUTA_DATOS

    registros = []
    incidencias = []
    resumen_bloques = []

    for archivo in sorted(ruta.glob("*.xlsx")):
        cultivo = identificar_cultivo(archivo.name)

        if cultivo is None:
            continue

        libro = pd.ExcelFile(archivo)

        for hoja in libro.sheet_names:
            df = pd.read_excel(
                archivo,
                sheet_name=hoja,
                header=None
            )

            encabezados = []

            # Buscar filas que contienen AÑO, ENE y FEB.
            for i in range(len(df)):
                fila = [
                    str(v).strip().upper()
                    if pd.notna(v) else ""
                    for v in df.iloc[i].tolist()
                ]

                for j, valor in enumerate(fila):
                    if (
                        valor in ("AÑO", "ANO")
                        and j + 2 < len(fila)
                        and fila[j + 1].startswith("ENE")
                        and fila[j + 2].startswith("FEB")
                    ):
                        encabezados.append((i, j))
                        break

            indicadores = CONFIGURACION[cultivo]

            if len(encabezados) != len(indicadores):
                raise ValueError(
                    f"{archivo.name}: se esperaban "
                    f"{len(indicadores)} bloques y se encontraron "
                    f"{len(encabezados)}"
                )

            for indice, (fila_inicio, col_anio) in enumerate(
                encabezados
            ):
                indicador = indicadores[indice]
                unidad = UNIDADES[indicador]

                fila_fin = (
                    encabezados[indice + 1][0]
                    if indice + 1 < len(encabezados)
                    else len(df)
                )

                anios = set()

                for i in range(fila_inicio + 1, fila_fin):
                    anio = convertir_numero(df.iloc[i, col_anio])

                    if (
                        anio is None
                        or not anio.is_integer()
                        or not 2012 <= anio <= 2023
                    ):
                        continue

                    anio = int(anio)

                    if anio in anios:
                        raise ValueError(
                            f"Año duplicado: {cultivo}, "
                            f"{indicador}, {anio}"
                        )

                    anios.add(anio)

                    for numero_mes, mes in enumerate(MESES, 1):
                        columna = col_anio + numero_mes
                        original = df.iloc[i, columna]
                        valor = convertir_numero(original)

                        base = {
                            "cultivo": cultivo,
                            "indicador": indicador,
                            "unidad": unidad,
                            "anio": anio,
                            "mes": mes,
                            "numero_mes": numero_mes,
                            "archivo_origen": archivo.name,
                            "hoja_origen": hoja,
                            "fila_excel": i + 1,
                        }

                        if valor is None:
                            incidencias.append({
                                **base,
                                "valor_origen": str(original)
                            })
                        else:
                            registros.append({
                                **base,
                                "valor": valor
                            })

                resumen_bloques.append({
                    "cultivo": cultivo,
                    "indicador": indicador,
                    "unidad": unidad,
                    "anios": len(anios)
                })

    return (
        pd.DataFrame(registros),
        pd.DataFrame(incidencias),
        pd.DataFrame(resumen_bloques)
    )


if __name__ == "__main__":
    datos, incidencias, bloques = (
        extraer_exportaciones_regionales()
    )

    print("===== EXTRACCION REGIONAL =====")
    print("Registros numericos:", len(datos))
    print("Valores ausentes:", len(incidencias))
    print("Bloques identificados:", len(bloques))

    print("\n===== COBERTURA POR BLOQUE =====")
    print(bloques.to_string(index=False))

    if not datos.empty:
        clave = ["cultivo", "indicador", "anio", "numero_mes"]

        print("\nDuplicados:", datos.duplicated(
            subset=clave
        ).sum())

        print("Valores negativos:", (
            datos["valor"] < 0
        ).sum())

        print("\nREGISTROS POR CULTIVO:")
        print(datos.groupby("cultivo").size())

    if not incidencias.empty:
        print("\nAUSENTES POR CULTIVO E INDICADOR:")
        print(
            incidencias.groupby(
                ["cultivo", "indicador"]
            ).size()
        )
