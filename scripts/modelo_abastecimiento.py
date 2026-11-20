"""Modelo de abastecimiento: pronóstico del ingreso de materia prima a planta.

Problema de negocio
    Danper programa cuánta alcachofa y espárrago comprar a proveedores
    terceros. En 2023 el volumen de alcachofa quedó 16,8 % debajo de la meta
    (Reporte de Sostenibilidad Danper 2023). Este script pronostica, con
    HORIZONTE meses de anticipación, el ingreso mensual de cada cultivo a las
    plantas agroindustriales de La Libertad (Gold: agroindustria_mensual,
    proceso INGRESO), que es el volumen que hay que asegurar.

Línea base (lo que se puede hacer sin modelo)
    naive_anual   mismo mes del año anterior
    prom_3a       promedio del mismo mes de los 3 años anteriores

Modelos (Spark MLlib)
    gbt           GBTRegressor
    rf            RandomForestRegressor
    lineal        LinearRegression (elastic net)
    Los modelos pronostican el log de la razón entre el mes y su nivel
    estacional de referencia (promedio del mismo mes en 3 años), ponderando
    cada mes por su tamaño en toneladas, y luego se convierte a toneladas.

Resultado (horizonte 3, pruebas 2019-2024, 132 meses)
    Ningún modelo supera a la línea base prom_3a (WAPE 36,9 %): lineal
    38,6 %, rf 40,7 %, gbt 42,2 %. La serie depende de choques anuales
    (clima, mercado) que no están en su historia; con 312 meses válidos el
    aprendizaje automático no agrega información. Ver README, sección 15.

Evaluación
    Validación hacia adelante por año: para cada año de prueba Y se entrena
    con los meses anteriores a Y y se pronostica Y. Todos los métodos se
    miden sobre los mismos meses. Métricas en toneladas:
        MAE          error absoluto medio mensual
        WAPE         suma |error| / suma real
        error_anual  (suma pronóstico - suma real) / suma real

Datos faltantes
    Los años completos en cero de la fuente no son producción nula sino
    vacíos del registro (espárrago 2016, alcachofa 2017-2018). Espárrago 2024
    es una copia celda a celda de 2023 en el Excel original. Esos meses se
    tratan como faltantes: no se usan como objetivo ni como variable.

Salidas
    Gold  ml_prediccion_ingreso   pronóstico de cada método por mes de prueba
    Gold  ml_metricas_modelo      métricas por cultivo, método y año
    Gold  ml_plan_ingreso         plan del año siguiente a los datos con el
                                  método recomendado (prom_3a) y su banda
    reportes/modelo/metricas.csv  copia de las métricas para el informe

Uso:
    python scripts/modelo_abastecimiento.py [--horizonte 3] [--desde 2019]
"""
from pathlib import Path
import argparse
import csv
import time

from pyspark.ml import Pipeline
from pyspark.ml.feature import Imputer, VectorAssembler
from pyspark.ml.regression import GBTRegressor, LinearRegression, RandomForestRegressor
from pyspark.sql import SparkSession, functions as F
from pyspark.sql.window import Window

import config

SERIES = {"ALCACHOFA": "PARA PROCESAR", "ESPARRAGO": "NATURAL"}
FALTANTES = {"ESPARRAGO": [2016, 2024], "ALCACHOFA": [2017, 2018]}
METODOS = ["naive_anual", "prom_3a", "gbt", "rf", "lineal"]
SEMILLA = 42
CSV_LOCAL = Path(__file__).resolve().parent.parent / "reportes" / "modelo" / "metricas.csv"


def crear_spark():
    spark = (
        SparkSession.builder.appName("Danper_Modelo_Abastecimiento")
        .config(map=config.SPARK_CONF)
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def serie_ingreso(spark):
    """Ingreso mensual por cultivo, con los meses faltantes en null."""
    gold = config.hdfs(config.GOLD)
    agro = spark.read.parquet(f"{gold}/agroindustria_mensual")
    condicion = F.lit(False)
    for cultivo, presentacion in SERIES.items():
        condicion |= (F.col("cultivo") == cultivo) & (F.col("presentacion") == presentacion)
    faltante = F.lit(False)
    for cultivo, anios in FALTANTES.items():
        faltante |= (F.col("cultivo") == cultivo) & F.col("anio").isin(anios)
    return (
        agro.filter((F.col("proceso") == "INGRESO") & condicion)
        .select("cultivo", "periodo", F.col("anio").cast("int").alias("anio"),
                F.col("numero_mes").cast("int").alias("mes"), "cantidad_t")
        .withColumn("real_t", F.when(faltante, None).otherwise(F.col("cantidad_t")))
        .drop("cantidad_t")
    )


def construir_variables(spark, horizonte):
    """Variables conocidas `horizonte` meses antes del mes a pronosticar."""
    gold = config.hdfs(config.GOLD)
    df = serie_ingreso(spark)
    w = Window.partitionBy("cultivo").orderBy("periodo")

    def rezago(n):
        return F.lag("real_t", n).over(w)

    # Rezagos estacionales: si el año anterior falta, se usa el siguiente.
    df = (
        df.withColumn("r12", rezago(12)).withColumn("r24", rezago(24))
        .withColumn("r36", rezago(36))
        .withColumn("mismo_mes_anterior", F.coalesce("r12", "r24", "r36"))
        .withColumn("mismo_mes_2a", F.coalesce("r24", "r36", "r12"))
        .withColumn(
            "prom_mismo_mes_3a",
            F.aggregate(F.array_compact(F.array("r12", "r24", "r36")),
                        F.lit(0.0), lambda a, x: a + x)
            / F.size(F.array_compact(F.array("r12", "r24", "r36"))),
        )
        # Lo último observado al momento de planificar.
        .withColumn("ultimo_mes", rezago(horizonte))
        .withColumn(
            "prom_reciente_3m",
            F.aggregate(
                F.array_compact(F.array(*[rezago(horizonte + i) for i in range(3)])),
                F.lit(0.0), lambda a, x: a + x)
            / F.size(F.array_compact(F.array(*[rezago(horizonte + i) for i in range(3)]))),
        )
        # Mismos meses recientes, pero un año antes (para medir la tendencia).
        .withColumn(
            "prom_reciente_3m_anterior",
            F.aggregate(
                F.array_compact(F.array(*[rezago(horizonte + 12 + i) for i in range(3)])),
                F.lit(0.0), lambda a, x: a + x)
            / F.size(F.array_compact(F.array(*[rezago(horizonte + 12 + i) for i in range(3)]))),
        )
        .withColumn("es_alcachofa", (F.col("cultivo") == "ALCACHOFA").cast("double"))
        .withColumn("mes_d", F.col("mes").cast("double"))
    )

    # Exportaciones regionales del cultivo, mismo mes del año anterior.
    exp = spark.read.parquet(f"{gold}/exportaciones_regionales")
    for anios in (1, 2):
        df = df.join(
            exp.select("cultivo", F.add_months("periodo", 12 * anios).alias("periodo"),
                       F.col("volumen_exportado_t").alias(f"export_{anios}a")),
            ["cultivo", "periodo"], "left")

    def log_razon(a, b):
        return F.log1p(F.col(a)) - F.log1p(F.col(b))

    # El modelo no pronostica toneladas sino cuánto se aparta el mes de su
    # nivel estacional de referencia (log de la razón). Los árboles no pueden
    # dar valores fuera del rango visto al entrenar; con la razón el
    # pronóstico sigue el crecimiento de la serie.
    df = (
        df.withColumn("referencia", F.col("prom_mismo_mes_3a"))
        .withColumn("objetivo", log_razon("real_t", "referencia"))
        .withColumn("tendencia_reciente", log_razon("prom_reciente_3m", "prom_reciente_3m_anterior"))
        .withColumn("anio_anterior_vs_ref", log_razon("mismo_mes_anterior", "referencia"))
        .withColumn("hace_2a_vs_ref", log_razon("mismo_mes_2a", "referencia"))
        .withColumn("tendencia_export", log_razon("export_1a", "export_2a"))
        .withColumn("peso_mes", F.log1p("referencia"))
    )

    # Línea base
    return (
        df.withColumn("pred_naive_anual", F.col("mismo_mes_anterior"))
        .withColumn("pred_prom_3a", F.col("prom_mismo_mes_3a"))
        .drop("r12", "r24", "r36")
    )


VARIABLES = ["es_alcachofa", "mes_d", "peso_mes", "tendencia_reciente",
             "anio_anterior_vs_ref", "hace_2a_vs_ref", "tendencia_export"]


def pipeline(modelo):
    imputadas = [f"{c}_i" for c in VARIABLES]
    return Pipeline(stages=[
        # Los nulos que quedan (primeros años, vacíos de la fuente) se
        # completan con la mediana del entrenamiento de cada corte.
        Imputer(inputCols=VARIABLES, outputCols=imputadas, strategy="median"),
        VectorAssembler(inputCols=imputadas, outputCol="features"),
        modelo,
    ])


def modelos():
    return {
        "gbt": GBTRegressor(labelCol="objetivo", weightCol="referencia", maxDepth=3, maxIter=60,
                            stepSize=0.1, seed=SEMILLA),
        "rf": RandomForestRegressor(labelCol="objetivo", weightCol="referencia", numTrees=200, maxDepth=5,
                                    seed=SEMILLA),
        "lineal": LinearRegression(labelCol="objetivo", weightCol="referencia",
                                   regParam=0.1, elasticNetParam=0.5, standardization=True),
    }


def validar_hacia_adelante(datos, anios):
    """Entrena con todo lo anterior a cada año y pronostica ese año."""
    # Solo meses con objetivo real y con al menos un año de historia.
    datos = datos.filter(F.col("real_t").isNotNull() & F.col("mismo_mes_anterior").isNotNull()).cache()
    resultados, importancias = [], {}
    for anio in anios:
        entrenamiento = datos.filter(F.col("anio") < anio)
        prueba = datos.filter(F.col("anio") == anio)
        if prueba.limit(1).count() == 0:
            continue
        pred = prueba
        for nombre, modelo in modelos().items():
            ajustado = pipeline(modelo.setPredictionCol(f"d_{nombre}")).fit(entrenamiento)
            pred = (ajustado.transform(pred).drop("features", *[f"{c}_i" for c in VARIABLES])
                    # De vuelta a toneladas: referencia x razón pronosticada.
                    .withColumn(f"pred_{nombre}",
                                F.expm1(F.log1p("referencia") + F.col(f"d_{nombre}"))))
            final = ajustado.stages[-1]
            importancias[nombre] = (final.featureImportances if hasattr(final, "featureImportances")
                                    else final.coefficients).toArray()
        n_ent, n_pru = entrenamiento.count(), prueba.count()
        print(f"  {anio}: entrenamiento {n_ent} meses, prueba {n_pru} meses")
        resultados.append(pred.withColumn("anio_prueba", F.lit(anio)))
    salida = resultados[0]
    for r in resultados[1:]:
        salida = salida.unionByName(r)
    for m in METODOS:
        salida = salida.withColumn(f"pred_{m}", F.greatest(F.col(f"pred_{m}"), F.lit(0.0)))
    return salida, importancias


def metricas(pred):
    """MAE, WAPE y error anual por cultivo, método y año (y 'TODOS')."""
    largo = pred.select(
        "cultivo", "anio_prueba", "real_t",
        F.explode(F.array(*[
            F.struct(F.lit(m).alias("metodo"), F.col(f"pred_{m}").alias("pred"))
            for m in METODOS])).alias("p"),
    ).select("cultivo", "anio_prueba", "real_t", "p.metodo", "p.pred")

    def agregar(df, cultivo, anio):
        return (
            df.withColumn("cultivo", F.lit(cultivo) if cultivo else F.col("cultivo"))
            .withColumn("anio_prueba", F.lit(anio).cast("string") if anio else F.col("anio_prueba").cast("string"))
            .groupBy("cultivo", "metodo", "anio_prueba")
            .agg(F.count("*").alias("n_meses"),
                 F.sum("real_t").alias("real_total_t"),
                 F.sum("pred").alias("pred_total_t"),
                 F.avg(F.abs(F.col("pred") - F.col("real_t"))).alias("mae_t"),
                 (F.sum(F.abs(F.col("pred") - F.col("real_t"))) / F.sum("real_t")).alias("wape"))
            .withColumn("error_anual",
                        (F.col("pred_total_t") - F.col("real_total_t")) / F.col("real_total_t"))
        )

    partes = [agregar(largo, None, None), agregar(largo, None, "TODOS"),
              agregar(largo, "TODOS", None), agregar(largo, "TODOS", "TODOS")]
    salida = partes[0]
    for p in partes[1:]:
        salida = salida.unionByName(p)
    return salida.orderBy("cultivo", "anio_prueba", "metodo")


def plan_siguiente(spark, met):
    """Plan del año siguiente al último dato, con el método recomendado.

    Para cada cultivo y mes: promedio de los 3 últimos años válidos de ese mes
    (prom_3a). La banda es ± el WAPE histórico de prom_3a en ese cultivo.
    """
    serie = serie_ingreso(spark)
    anio_plan = serie.agg(F.max("anio")).first()[0] + 1
    w = Window.partitionBy("cultivo", "mes").orderBy(F.desc("anio"))
    wape = (met.filter((F.col("metodo") == "prom_3a") & (F.col("anio_prueba") == "TODOS"))
            .select("cultivo", F.col("wape").alias("wape_historico"),
                    F.col("error_anual").alias("sesgo_historico")))
    return (
        serie.filter(F.col("real_t").isNotNull())
        .withColumn("orden", F.row_number().over(w)).filter(F.col("orden") <= 3)
        .groupBy("cultivo", "mes")
        .agg(F.avg("real_t").alias("plan_t"),
             F.concat_ws(",", F.sort_array(F.collect_list("anio"))).alias("anios_base"))
        .join(wape, "cultivo", "left")
        .withColumn("anio", F.lit(anio_plan))
        .withColumn("periodo", F.make_date(F.lit(anio_plan), "mes", F.lit(1)))
        .withColumn("minimo_t", F.col("plan_t") * (1 - F.col("wape_historico")))
        .withColumn("maximo_t", F.col("plan_t") * (1 + F.col("wape_historico")))
        .withColumn("metodo", F.lit("prom_3a"))
        .withColumn("generado_en", F.current_timestamp())
        .select("cultivo", "periodo", "anio", "mes", "plan_t", "minimo_t", "maximo_t",
                "metodo", "anios_base", "wape_historico", "sesgo_historico", "generado_en")
        .orderBy("cultivo", "mes")
    )


def guardar_csv(filas, columnas):
    CSV_LOCAL.parent.mkdir(parents=True, exist_ok=True)
    with CSV_LOCAL.open("w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(columnas)
        for fila in filas:
            escritor.writerow([round(v, 4) if isinstance(v, float) else v for v in fila])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--horizonte", type=int, default=3,
                    help="meses de anticipación del pronóstico (por defecto 3)")
    ap.add_argument("--desde", type=int, default=2019, help="primer año de prueba")
    ap.add_argument("--hasta", type=int, default=2024, help="último año de prueba")
    args = ap.parse_args()

    inicio = time.time()
    spark = crear_spark()
    gold = config.hdfs(config.GOLD)

    print(f"Horizonte: {args.horizonte} meses. Años de prueba: {args.desde}-{args.hasta}")
    datos = construir_variables(spark, args.horizonte)
    pred, importancias = validar_hacia_adelante(datos, range(args.desde, args.hasta + 1))

    columnas_pred = ["cultivo", "periodo", "anio", "mes", "anio_prueba", "real_t",
                     *[f"pred_{m}" for m in METODOS]]
    pred = (pred.select(*columnas_pred)
            .withColumn("horizonte_meses", F.lit(args.horizonte))
            .orderBy("cultivo", "periodo").cache())
    met = (metricas(pred).withColumn("horizonte_meses", F.lit(args.horizonte))
           .withColumn("generado_en", F.current_timestamp()).cache())

    pred.coalesce(1).write.mode("overwrite").parquet(f"{gold}/ml_prediccion_ingreso")
    met.coalesce(1).write.mode("overwrite").parquet(f"{gold}/ml_metricas_modelo")
    plan = plan_siguiente(spark, met)
    plan.coalesce(1).write.mode("overwrite").parquet(f"{gold}/ml_plan_ingreso")

    columnas_csv = ["cultivo", "metodo", "anio_prueba", "n_meses", "real_total_t",
                    "pred_total_t", "mae_t", "wape", "error_anual", "horizonte_meses"]
    filas = met.select(*columnas_csv).collect()
    guardar_csv(filas, columnas_csv)

    print("\nResumen (todos los años de prueba):")
    print(f"{'cultivo':<10} {'método':<12} {'meses':>5} {'MAE t':>8} {'WAPE':>7} {'err. anual':>10}")
    for f in filas:
        if f["anio_prueba"] == "TODOS":
            print(f"{f['cultivo']:<10} {f['metodo']:<12} {f['n_meses']:>5} "
                  f"{f['mae_t']:>8.0f} {f['wape']:>7.1%} {f['error_anual']:>+10.1%}")

    print("\nImportancia de variables (último corte):")
    for nombre, valores in importancias.items():
        orden = sorted(zip(VARIABLES, valores), key=lambda x: -x[1])
        print(f"  {nombre}: " + ", ".join(f"{v} {i:.2f}" for v, i in orden))

    print("\nPlan del año siguiente (prom_3a):")
    for f in (spark.read.parquet(f"{gold}/ml_plan_ingreso")
              .groupBy("cultivo", "anio", "anios_base").agg(F.sum("plan_t").alias("t"))
              .orderBy("cultivo").collect()):
        print(f"  {f['cultivo']} {f['anio']}: {f['t']:,.0f} t (base {f['anios_base']})")

    print(f"\nGold: {gold}/ml_prediccion_ingreso, {gold}/ml_metricas_modelo, {gold}/ml_plan_ingreso")
    print(f"CSV:  {CSV_LOCAL}")
    print(f"Tiempo: {time.time() - inicio:.0f} s")
    spark.stop()


if __name__ == "__main__":
    main()
