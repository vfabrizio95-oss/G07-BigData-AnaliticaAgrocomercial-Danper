from pathlib import Path
import re
import pandas as pd

RUTA_DATOS = Path.home() / "proyecto_danper/datasets/agroindustria"

CUADROS = {
    7: ("INGRESO", "PARA PROCESAR"),
    8: ("UTILIZACION", "PARA PROCESAR"),
    9: ("PRODUCCION", "FRESCO"),
    10: ("PRODUCCION", "CONSERVA"),
    11: ("PRODUCCION", "CONGELADO"),
    12: ("VENTA", "FRESCO"),
    13: ("VENTA", "CONSERVA"),
    14: ("VENTA", "CONGELADO"),
    64: ("INGRESO", "NATURAL"),
    65: ("UTILIZACION", "NATURAL"),
    66: ("PRODUCCION", "CONSERVA"),
    67: ("PRODUCCION", "CONGELADO"),
    68: ("PRODUCCION", "FRESCO"),
    69: ("PRODUCCION", "HARINA"),
    70: ("VENTA", "CONSERVA"),
    71: ("VENTA", "CONGELADO"),
    72: ("VENTA", "FRESCO"),
    73: ("VENTA", "HARINA"),
}

MESES = [
    "ENE", "FEB", "MAR", "ABR", "MAY", "JUN",
    "JUL", "AGO", "SET", "OCT", "NOV", "DIC"
]


def convertir_numero(valor):
    if pd.isna(valor):
        return None
    if isinstance(valor, str):
        valor = valor.strip()
        if valor in ("", "--", "-", "—"):
            return None
    try:
        return float(valor)
    except (ValueError, TypeError):
        return None


def extraer_agroindustria(ruta=None):
    ruta = Path(ruta) if ruta is not None else RUTA_DATOS
    registros = []
    incidencias = []
    cuadros_encontrados = set()

    for archivo in sorted(ruta.glob("*.xlsx")):
        cultivo = (
            "ALCACHOFA" if "ALCACHOFA" in archivo.name.upper()
            else "ESPARRAGO" if "ESPARRAGO" in archivo.name.upper()
            else None
        )

        if cultivo is None:
            continue

        libro = pd.ExcelFile(archivo)

        for hoja in libro.sheet_names:
            df = pd.read_excel(
                archivo, sheet_name=hoja, header=None
            )

            cuadro = None
            encabezado = False

            for i in range(len(df)):
                primera = df.iloc[i, 0]
                texto = str(primera).strip().upper()

                coincidencia = re.search(
                    r"CUADRO\s*N[°ºo.]?\s*0*(\d+)",
                    texto
                )

                if coincidencia:
                    cuadro = int(coincidencia.group(1))
                    encabezado = False
                    if cuadro not in CUADROS:
                        raise ValueError(
                            f"Cuadro no reconocido: {cuadro}"
                        )
                    cuadros_encontrados.add((cultivo, cuadro))
                    continue

                if texto == "AÑO" and cuadro is not None:
                    encabezado = True
                    continue

                if not encabezado:
                    continue

                try:
                    anio_num = float(primera)
                    if not anio_num.is_integer():
                        continue
                    anio = int(anio_num)
                except (ValueError, TypeError):
                    continue

                if not 2010 <= anio <= 2024:
                    continue

                proceso, presentacion = CUADROS[cuadro]

                for numero_mes, mes in enumerate(MESES, start=1):
                    valor_origen = df.iloc[i, numero_mes + 1]
                    cantidad = convertir_numero(valor_origen)

                    if cantidad is None:
                        incidencias.append({
                            "cultivo": cultivo,
                            "cuadro": cuadro,
                            "anio": anio,
                            "mes": mes,
                            "valor_origen": str(valor_origen)
                        })
                        continue

                    registros.append({
                        "cultivo": cultivo,
                        "proceso": proceso,
                        "presentacion": presentacion,
                        "anio": anio,
                        "mes": mes,
                        "numero_mes": numero_mes,
                        "cantidad_t": cantidad,
                        "cuadro_origen": cuadro,
                        "archivo_origen": archivo.name,
                        "hoja_origen": hoja
                    })

    return (
        pd.DataFrame(registros),
        pd.DataFrame(incidencias),
        cuadros_encontrados
    )


if __name__ == "__main__":
    datos, incidencias, cuadros = extraer_agroindustria()

    print("===== EXTRACCION AGROINDUSTRIAL =====")
    print("Registros mensuales:", len(datos))
    print("Cuadros identificados:", len(cuadros))
    print("Valores ausentes/no numericos:", len(incidencias))

    if not datos.empty:
        print("\nREGISTROS POR CULTIVO:")
        print(datos.groupby("cultivo").size())

        print("\nREGISTROS POR PROCESO:")
        print(datos.groupby(["cultivo", "proceso"]).size())

        print("\nPRIMEROS REGISTROS:")
        print(datos.head(5).to_string(index=False))

    if not incidencias.empty:
        print("\nEJEMPLOS DE VALORES NO EXTRAIDOS:")
        print(incidencias.head(10).to_string(index=False))
