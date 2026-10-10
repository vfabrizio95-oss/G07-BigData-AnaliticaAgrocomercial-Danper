from pathlib import Path
import pandas as pd

# Configuración de rutas
RUTA_DATOS = Path.home() / "proyecto_danper/datasets/produccion"

def extraer_datos_agricolas(ruta_datos=RUTA_DATOS):
    registros = []

    for archivo in sorted(ruta_datos.glob("*.xlsx")):
        provincia = (
            archivo.stem
            .replace("PROVINCIA ", "")
            .replace("_2024-2025", "")
            .replace("_", " ")
        )

        excel = pd.ExcelFile(archivo)

        for hoja in excel.sheet_names:
            if hoja.strip().lower().startswith("provincia"):
                continue

            df = pd.read_excel(
                archivo,
                sheet_name=hoja,
                header=None
            )

            codigo_actual = None
            cultivo_actual = None

            for i in range(11, len(df)):
                codigo = df.iloc[i, 0]
                cultivo = df.iloc[i, 1]
                variable = df.iloc[i, 2]

                if pd.notna(codigo) and pd.notna(cultivo):
                    codigo_actual = str(codigo).strip()
                    cultivo_actual = str(cultivo).strip()

                if pd.isna(variable) or cultivo_actual is None:
                    continue

                for columna in range(4, 21):
                    valor = pd.to_numeric(
                        df.iloc[i, columna],
                        errors="coerce"
                    )

                    if pd.notna(valor):
                        registros.append({
                            "provincia": provincia,
                            "distrito": hoja,
                            "codigo_cultivo": codigo_actual,
                            "cultivo": cultivo_actual,
                            "variable": str(variable).strip(),
                            "columna_origen": columna,
                            "mes_origen": str(
                                df.iloc[10, columna]
                            ).strip(),
                            "valor": float(valor),
                            "archivo_origen": archivo.name
                        })

    return pd.DataFrame(registros)


if __name__ == "__main__":
    datos = extraer_datos_agricolas()

    print("Registros extraídos:", len(datos))
    print("Provincias:", datos["provincia"].nunique())
    print("Cultivos:", datos["cultivo"].nunique())
    print(datos.head())
