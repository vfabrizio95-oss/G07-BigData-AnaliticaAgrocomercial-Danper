"""Pruebas de escalabilidad y de caché del procesamiento Gold (Spark sobre HDFS).

Escalabilidad
    Replica Silver ×F (F = 1, 10, 100, 1000 ...) y ejecuta sobre cada réplica
    un trabajo representativo de Gold: pivot de producción y de exportaciones,
    agregaciones, ventana (lag) sobre costos, join con una dimensión de tiempo,
    KPI anual y escritura en HDFS.

    Cada copia lleva una columna `replica` que forma parte de todas las claves
    de agrupación, ventana y join, y sus valores se alteran levemente. Así las
    réplicas no se fusionan en distinct/pivot y el trabajo crece con F. El
    script comprueba que las filas de salida sean F veces las de ×1.

    Se puede variar también el paralelismo: --nucleos (local[n]) en una sola
    máquina o --executores (spark.executor.instances) en un cluster YARN.

Caché
    Prepara una tabla analítica (pivot de producción ×F) y ejecuta 5 consultas
    de KPI sin caché y con caché. El tiempo de llenar la caché se mide aparte.

Medición
    - Cada escenario corre en su propia aplicación Spark (subproceso), con
      1 ejecución de calentamiento y --repeticiones mediciones.
    - Tiempo de pared por ejecución y métricas de Spark tomadas de su API REST
      (tiempo de executors, bytes leídos, shuffle, tareas) y memoria JVM pico
      de los executors. No se usa psutil.
    - spark.eventLog.enabled guarda cada aplicación en DANPER_SPARK_EVENTS
      (por defecto /danper/spark-events en HDFS) para el Spark History Server.

Salidas (se agregan filas; la columna `entorno` distingue local y AWS)
    reportes/escalabilidad/escalabilidad.csv
    reportes/escalabilidad/cache.csv

Uso:
    python scripts/prueba_escalabilidad.py --prueba escalabilidad \\
        --factores 1 10 100 1000 --nucleos 8
    python scripts/prueba_escalabilidad.py --prueba escalabilidad \\
        --factores 1000 --nucleos 1 2 4 8
    python scripts/prueba_escalabilidad.py --prueba cache --factores 1000
    # En el cluster: DANPER_SPARK_MASTER=yarn ... --executores 1 2 3 --entorno aws
"""
from datetime import datetime
from pathlib import Path
import argparse
import csv
import json
import os
import platform
import statistics
import subprocess
import sys
import time
import urllib.request

import config

RAIZ_PRUEBAS = config.PRUEBAS_ESCALABILIDAD
EVENTOS = os.environ.get("DANPER_SPARK_EVENTS", f"{config.HDFS_BASE}/spark-events")
REPORTES = Path(__file__).resolve().parent.parent / "reportes" / "escalabilidad"
FUENTES = ["produccion", "exportaciones/regionales", "agroindustria", "costos",
           "exportaciones/danper"]
CULTIVOS = ["ESPARRAGO", "ALCACHOFA", "ARANDANO", "PALTA", "UVA"]
VARIABLES = {"Produccion (t.)": "produccion_t", "Precio Chacra (S/Kg.)": "precio_chacra_s_kg",
             "Cosechas (ha.)": "cosechas_ha", "Siembras (ha.)": "siembras_ha",
             "Sup.Verde (ha.)": "superficie_verde_ha",
             "Sup Perdida (ha.)": "superficie_perdida_ha",
             "Rendimiento (Kg./ha.)": "rendimiento_kg_ha"}

COLUMNAS = ["fecha", "entorno", "prueba", "modo", "master", "nucleos", "executores",
            "memoria_executor", "factor", "fase", "repeticion", "segundos",
            "filas_entrada", "filas_salida", "mb_entrada", "mb_shuffle_lectura",
            "mb_shuffle_escritura", "segundos_executors", "tareas",
            "memoria_pico_mb", "app_id"]


# ---------------------------------------------------------------- Spark
def crear_spark(nombre, master=None, executores=None, eventos=True):
    from pyspark.sql import SparkSession

    b = SparkSession.builder.appName(nombre).config(map=config.SPARK_CONF)
    if master:
        b = b.master(master)
    if executores:
        b = (b.config("spark.executor.instances", str(executores))
             .config("spark.dynamicAllocation.enabled", "false"))
    if eventos:
        b = (b.config("spark.eventLog.enabled", "true")
             .config("spark.eventLog.dir", config.hdfs(EVENTOS)))
    memoria = os.environ.get("DANPER_DRIVER_MEMORY", "4g")
    b = (b.config("spark.driver.memory", memoria)
         .config("spark.sql.adaptive.enabled", "true")
         .config("spark.ui.showConsoleProgress", "false"))
    spark = b.getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def fs_y_ruta(spark):
    jvm = spark._jvm
    fs = jvm.org.apache.hadoop.fs.FileSystem.get(
        jvm.java.net.URI(config.HDFS_URI), spark._jsc.hadoopConfiguration())
    return fs, jvm.org.apache.hadoop.fs.Path


class MetricasSpark:
    """Lee la API REST de la interfaz de Spark de la aplicación actual."""

    def __init__(self, spark):
        self.sc = spark.sparkContext
        # El script corre en la máquina del driver (modo client). Se usa
        # 127.0.0.1: el nombre del equipo puede resolver primero a IPv6 y la
        # interfaz de Spark escucha en IPv4 (cada consulta esperaría un timeout).
        puerto = self.sc.uiWebUrl.rsplit(":", 1)[1]
        self.base = (f"http://127.0.0.1:{puerto}/api/v1/applications/"
                     f"{self.sc.applicationId}")

    def _get(self, ruta):
        with urllib.request.urlopen(f"{self.base}/{ruta}", timeout=30) as r:
            return json.load(r)

    def de_grupo(self, grupo):
        """Suma las métricas de las etapas de los jobs de un grupo."""
        trabajos = [j for j in self._get("jobs") if j.get("jobGroup") == grupo]
        etapas = {s for j in trabajos for s in j["stageIds"]}
        total = dict(bytes_entrada=0, shuffle_lectura=0, shuffle_escritura=0,
                     ms_executors=0, tareas=0)
        for sid in etapas:
            for intento in self._get(f"stages/{sid}"):
                if intento.get("status") not in ("COMPLETE",):
                    continue
                total["bytes_entrada"] += intento.get("inputBytes", 0)
                total["shuffle_lectura"] += intento.get("shuffleReadBytes", 0)
                total["shuffle_escritura"] += intento.get("shuffleWriteBytes", 0)
                total["ms_executors"] += intento.get("executorRunTime", 0)
                total["tareas"] += intento.get("numCompleteTasks", 0)
        return total

    def entorno(self):
        ejecutores = self._get("allexecutors")
        trabajadores = [e for e in ejecutores if e["id"] != "driver"]
        pico = max((e.get("peakMemoryMetrics", {}).get("JVMHeapMemory", 0)
                    for e in (trabajadores or ejecutores)), default=0)
        nucleos = sum(e.get("totalCores", 0) for e in (trabajadores or ejecutores))
        return dict(executores=len(trabajadores), nucleos=nucleos,
                    memoria_pico_mb=round(pico / 2**20, 1))


# ----------------------------------------------------------- Generación
def generar(args):
    """Crea Silver ×F en HDFS (si no existe) y la carpeta de eventos."""
    from pyspark.sql import functions as F

    spark = crear_spark("Danper_Escalabilidad_Generar", eventos=False)
    fs, Path_ = fs_y_ruta(spark)
    fs.mkdirs(Path_(EVENTOS))
    filas = []
    silver = config.hdfs(config.SILVER)
    for factor in args.factores:
        destino = f"{RAIZ_PRUEBAS}/silver_x{factor}"
        if fs.exists(Path_(f"{destino}/_COMPLETO")):
            print(f"Silver ×{factor}: ya existe")
            continue
        inicio = time.time()
        # Las réplicas son el lado grande del cruce y Silver (pocos MB) se
        # difunde a todos los executors: así el cruce usa todos los núcleos y
        # no solo tantos como archivos tenga cada fuente.
        particiones = max(1, min(spark.sparkContext.defaultParallelism * 2, factor))
        replicas = spark.range(0, factor, numPartitions=particiones).select(
            F.col("id").cast("int").alias("replica"))
        total = 0
        for fuente in FUENTES:
            df = spark.read.parquet(f"{silver}/{fuente}")
            columna = "valor" if "valor" in df.columns else (
                "cantidad_t" if "cantidad_t" in df.columns else "fob_usd")
            rep = (replicas.crossJoin(F.broadcast(df))
                   # Valores levemente distintos por réplica (no son copias exactas).
                   .withColumn(columna, F.col(columna) * (1 + (F.col("replica") % 7) * 0.01)))
            rep.write.mode("overwrite").parquet(
                config.hdfs(f"{destino}/{fuente}"))
            total += df.count() * factor
        fs.create(Path_(f"{destino}/_COMPLETO")).close()
        segundos = time.time() - inicio
        mb = fs.getContentSummary(Path_(destino)).getLength() / 2**20
        print(f"Silver ×{factor}: {total:,} filas, {mb:,.1f} MB, {segundos:.1f} s")
        filas.append(dict(factor=factor, segundos=round(segundos, 2),
                          filas_entrada=total, mb_entrada=round(mb, 1)))
    spark.stop()
    return filas


# ------------------------------------------------------ Trabajo de Gold
def trabajo_gold(spark, factor, salida):
    """Trabajo representativo de Gold sobre Silver ×factor. Devuelve filas escritas."""
    from pyspark.sql import functions as F
    from pyspark.sql.window import Window

    base = config.hdfs(f"{RAIZ_PRUEBAS}/silver_x{factor}")
    leer = lambda f: spark.read.parquet(f"{base}/{f}")

    prod = (leer("produccion").withColumn("cultivo", F.upper(F.trim("cultivo")))
            .filter(F.col("cultivo").isin(CULTIVOS) & F.col("periodo").isNotNull())
            .groupBy("replica", "provincia", "distrito", "cultivo", "periodo")
            .pivot("variable", list(VARIABLES)).agg(F.first("valor", ignorenulls=True)))
    for k, v in VARIABLES.items():
        prod = prod.withColumnRenamed(k, v)

    exp = (leer("exportaciones/regionales").withColumn("cultivo", F.upper(F.trim("cultivo")))
           .filter(F.col("cultivo").isin(CULTIVOS) & F.col("numero_mes").between(1, 12))
           .groupBy("replica", "cultivo", "anio", "numero_mes")
           .pivot("indicador", ["VOLUMEN", "VALOR_FOB", "PRECIO_FOB"])
           .agg(F.first("valor", ignorenulls=True))
           .withColumn("periodo", F.make_date(F.col("anio").cast("int"),
                                              F.col("numero_mes").cast("int"), F.lit(1))))

    agro = (leer("agroindustria").withColumn("cultivo", F.upper(F.trim("cultivo")))
            .groupBy("replica", "cultivo", "anio", "numero_mes", "proceso", "presentacion")
            .agg(F.sum("cantidad_t").alias("cantidad_t")))

    w = Window.partitionBy("replica", "region", "tipo_costo").orderBy("periodo")
    costos = (leer("costos").withColumn("periodo", F.make_date("anio", "numero_mes", F.lit(1)))
              .withColumn("valor_anterior", F.lag("valor").over(w))
              .withColumn("variacion", F.col("valor") / F.col("valor_anterior") - 1))

    danper = (leer("exportaciones/danper").withColumn("pais", F.upper(F.trim("pais")))
              .groupBy("replica", "pais", "periodo").agg(F.sum("fob_usd").alias("fob_usd")))

    dim_tiempo = (prod.select("replica", "periodo")
                  .unionByName(exp.select("replica", "periodo")).distinct()
                  .withColumn("tiempo_id", F.year("periodo") * 100 + F.month("periodo"))
                  .withColumn("trimestre", F.quarter("periodo")))
    fact_prod = prod.join(dim_tiempo, ["replica", "periodo"], "left")
    kpi = (fact_prod.groupBy("replica", "cultivo", F.year("periodo").alias("anio"))
           .agg(F.sum("produccion_t").alias("produccion_t"),
                F.avg("precio_chacra_s_kg").alias("precio_medio"),
                F.countDistinct("distrito").alias("distritos")))

    tablas = dict(fact_produccion=fact_prod, exportaciones=exp, agroindustria=agro,
                  costos=costos, exportaciones_danper=danper, kpi_produccion=kpi)
    filas = 0
    for nombre, df in tablas.items():
        df.write.mode("overwrite").parquet(config.hdfs(f"{salida}/{nombre}"))
        filas += spark.read.parquet(config.hdfs(f"{salida}/{nombre}")).count()
    return filas


def consultas_cache(spark, factor, usar_cache):
    """Tabla analítica de producción y 5 consultas de KPI sobre ella."""
    from pyspark.sql import functions as F

    base = config.hdfs(f"{RAIZ_PRUEBAS}/silver_x{factor}")
    tabla = (spark.read.parquet(f"{base}/produccion")
             .withColumn("cultivo", F.upper(F.trim("cultivo")))
             .filter(F.col("cultivo").isin(CULTIVOS) & F.col("periodo").isNotNull())
             .groupBy("replica", "provincia", "distrito", "cultivo", "periodo")
             .pivot("variable", list(VARIABLES)).agg(F.first("valor", ignorenulls=True)))
    for k, v in VARIABLES.items():
        tabla = tabla.withColumnRenamed(k, v)
    preparacion = 0.0
    if usar_cache:
        inicio = time.time()
        # La tabla sale del pivot con spark.sql.shuffle.partitions (200)
        # particiones; guardada así, cada consulta con shuffle pagaría 200
        # tareas pequeñas. Se junta en 2 particiones por núcleo (sin shuffle).
        n = spark.sparkContext.defaultParallelism * 2
        tabla = tabla.coalesce(n).cache()
        tabla.count()
        preparacion = time.time() - inicio

    def consultas():
        return [
            tabla.groupBy("cultivo", F.year("periodo")).agg(F.sum("produccion_t")),
            tabla.groupBy("provincia").agg(F.sum("produccion_t"), F.avg("rendimiento_kg_ha")),
            tabla.groupBy("replica", "distrito").agg(F.sum("produccion_t").alias("t"))
                 .orderBy(F.desc("t")).limit(20),
            tabla.groupBy("periodo", "cultivo").agg(F.avg("precio_chacra_s_kg")),
            tabla.filter(F.col("produccion_t") > 0)
                 .groupBy("cultivo").agg(F.countDistinct("replica", "distrito")),
        ]
    return tabla, preparacion, consultas


# ---------------------------------------------------- Escenario (hijo)
def escenario(args):
    """Corre un escenario en esta aplicación Spark e imprime filas JSON."""
    master = f"local[{args.nucleo}]" if args.nucleo else config.SPARK_MASTER
    nombre = (f"Danper_{args.prueba}_x{args.factor}_"
              f"{'n' + str(args.nucleo) if args.nucleo else 'e' + str(args.executor or 'def')}"
              f"{'_' + args.modo if args.modo else ''}")
    spark = crear_spark(nombre, master=master, executores=args.executor)
    metricas = MetricasSpark(spark)
    sc = spark.sparkContext
    base = dict(prueba=args.prueba, modo=args.modo or "", factor=args.factor,
                master=sc.master, memoria_executor=sc.getConf().get("spark.executor.memory", ""),
                app_id=sc.applicationId)
    filas_entrada = sum(
        spark.read.parquet(config.hdfs(f"{RAIZ_PRUEBAS}/silver_x{args.factor}/{f}")).count()
        for f in FUENTES)
    mb_entrada = 0.0
    fs, Path_ = fs_y_ruta(spark)
    mb_entrada = fs.getContentSummary(
        Path_(f"{RAIZ_PRUEBAS}/silver_x{args.factor}")).getLength() / 2**20

    resultados = []
    referencia_filas = None
    if args.prueba == "cache":
        tabla, preparacion, consultas = consultas_cache(spark, args.factor, args.modo == "con_cache")
        if args.modo == "con_cache":
            resultados.append(dict(fase="preparacion_cache", repeticion=0,
                                   segundos=round(preparacion, 3), filas_salida=tabla.count()))

    for rep in range(args.repeticiones + 1):
        grupo = f"rep{rep}"
        sc.setJobGroup(grupo, grupo)
        inicio = time.time()
        if args.prueba == "escalabilidad":
            filas = trabajo_gold(spark, args.factor, f"{RAIZ_PRUEBAS}/salida_{sc.applicationId}")
        else:
            filas = sum(len(q.collect()) for q in consultas())
        segundos = time.time() - inicio
        m = metricas.de_grupo(grupo)
        resultados.append(dict(
            fase="calentamiento" if rep == 0 else "medicion", repeticion=rep,
            segundos=round(segundos, 3), filas_salida=filas,
            mb_shuffle_lectura=round(m["shuffle_lectura"] / 2**20, 2),
            mb_shuffle_escritura=round(m["shuffle_escritura"] / 2**20, 2),
            segundos_executors=round(m["ms_executors"] / 1000, 2), tareas=m["tareas"]))
        referencia_filas = filas
    sc.setJobGroup("fin", "fin")
    if args.prueba == "escalabilidad":
        fs.delete(Path_(f"{RAIZ_PRUEBAS}/salida_{sc.applicationId}"), True)
    entorno = metricas.entorno()
    spark.stop()
    for r in resultados:
        fila = dict(base, filas_entrada=filas_entrada, mb_entrada=round(mb_entrada, 1), **entorno)
        fila.update(r)
        print("RESULTADO " + json.dumps(fila), flush=True)
    return referencia_filas


# ---------------------------------------------------------- Orquestador
def correr_escenario(args, factor, nucleo=None, executor=None, modo=None):
    cmd = [sys.executable, __file__, "--_escenario", "--prueba", args.prueba,
           "--factor", str(factor), "--repeticiones", str(args.repeticiones)]
    if nucleo:
        cmd += ["--nucleo", str(nucleo)]
    if executor:
        cmd += ["--executor", str(executor)]
    if modo:
        cmd += ["--modo", modo]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    filas = [json.loads(l[len("RESULTADO "):]) for l in proc.stdout.splitlines()
             if l.startswith("RESULTADO ")]
    if proc.returncode != 0 or not filas:
        sys.stderr.write(proc.stderr[-3000:])
        raise RuntimeError(f"Falló el escenario ×{factor} {nucleo or executor or ''} {modo or ''}")
    return filas


def guardar(nombre, filas, entorno):
    REPORTES.mkdir(parents=True, exist_ok=True)
    ruta = REPORTES / nombre
    nuevo = not ruta.exists()
    fecha = datetime.now().isoformat(timespec="seconds")
    with ruta.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS, extrasaction="ignore")
        if nuevo:
            w.writeheader()
        for fila in filas:
            w.writerow({"fecha": fecha, "entorno": entorno, **fila})
    return ruta


def resumen(filas):
    grupos = {}
    for f in filas:
        if f["fase"] == "medicion":
            clave = (f["factor"], f["nucleos"], f["executores"], f["modo"])
            grupos.setdefault(clave, []).append(f)
    print(f"\n{'factor':>7} {'núcleos':>7} {'exec':>4} {'modo':<10} {'mediana s':>9} "
          f"{'mín':>7} {'máx':>7} {'filas salida':>13} {'shuffle MB':>10} {'mem MB':>7}")
    for (factor, nucleos, execs, modo), fs_ in sorted(grupos.items()):
        t = [f["segundos"] for f in fs_]
        print(f"{factor:>7} {nucleos:>7} {execs:>4} {modo:<10} {statistics.median(t):>9.2f} "
              f"{min(t):>7.2f} {max(t):>7.2f} {fs_[0]['filas_salida']:>13,} "
              f"{fs_[0]['mb_shuffle_escritura']:>10.1f} {fs_[0]['memoria_pico_mb']:>7.0f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--prueba", choices=["escalabilidad", "cache"], default="escalabilidad")
    ap.add_argument("--factores", type=int, nargs="+", default=[1, 10, 100, 1000])
    ap.add_argument("--nucleos", type=int, nargs="+",
                    help="local[n] para cada valor (una sola máquina)")
    ap.add_argument("--executores", type=int, nargs="+",
                    help="spark.executor.instances para cada valor (cluster YARN)")
    ap.add_argument("--repeticiones", type=int, default=3)
    ap.add_argument("--entorno", default=f"local-{platform.node()}",
                    help="etiqueta del entorno en los CSV (por ejemplo aws-3workers)")
    # Uso interno: un escenario por subproceso.
    ap.add_argument("--_escenario", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--factor", type=int, help=argparse.SUPPRESS)
    ap.add_argument("--nucleo", type=int, help=argparse.SUPPRESS)
    ap.add_argument("--executor", type=int, help=argparse.SUPPRESS)
    ap.add_argument("--modo", help=argparse.SUPPRESS)
    args = ap.parse_args()

    if args._escenario:
        escenario(args)
        return
    if args.nucleos and args.executores:
        ap.error("Use --nucleos (local) o --executores (cluster), no ambos")

    inicio = time.time()
    print(f"===== PRUEBA DE {args.prueba.upper()} =====  entorno: {args.entorno}")
    generadas = generar(args)
    if generadas:
        guardar("escalabilidad.csv",
                [dict(g, prueba="generacion", fase="generacion", repeticion=0) for g in generadas],
                args.entorno)

    variantes = ([("nucleo", n) for n in args.nucleos] if args.nucleos else
                 [("executor", e) for e in args.executores] if args.executores else [(None, None)])
    modos = ["sin_cache", "con_cache"] if args.prueba == "cache" else [None]
    todas = []
    for factor in args.factores:
        for tipo, valor in variantes:
            for modo in modos:
                t0 = time.time()
                filas = correr_escenario(args, factor, modo=modo,
                                         **({tipo: valor} if tipo else {}))
                med = [f["segundos"] for f in filas if f["fase"] == "medicion"]
                print(f"×{factor:<5} {tipo or ''} {valor or '':<3} {modo or '':<10} "
                      f"mediana {statistics.median(med):.2f} s "
                      f"(escenario {time.time() - t0:.0f} s)", flush=True)
                todas += filas

    if args.prueba == "escalabilidad":
        # Las réplicas no deben fusionarse: filas de salida proporcionales al factor.
        por_factor = {f["factor"]: f["filas_salida"] for f in todas}
        if 1 in por_factor:
            for factor, filas in por_factor.items():
                esperado = por_factor[1] * factor
                estado = "OK" if filas == esperado else "DISTINTO"
                print(f"Filas de salida ×{factor}: {filas:,} (esperado {esperado:,}) {estado}")

    ruta = guardar("escalabilidad.csv" if args.prueba == "escalabilidad" else "cache.csv",
                   todas, args.entorno)
    resumen(todas)
    print(f"\nCSV: {ruta}\nEventos de Spark: {config.hdfs(EVENTOS)}")
    print(f"Tiempo total: {time.time() - inicio:.0f} s")


if __name__ == "__main__":
    main()
