#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ETL Gold Danper (Spark 3.5.x, HDFS on-premise).

Modo predeterminado: --check (SOLO LECTURA). Para construir componentes
faltantes deliberadamente: --build-missing. Nunca sobrescribe rutas existentes.
El script no ha sido ejecutado en el cluster del usuario: probar --check primero.
"""
import argparse
from pyspark.sql import SparkSession, functions as F
from pyspark.sql.window import Window

EXPECTED = {
 'produccion_mensual': (561,13), 'exportaciones_regionales': (720,7),
 'exportaciones_danper': (495,6), 'agroindustria_mensual': (3134,7),
 'costos_mensuales': (6292,7), 'abastecimiento_mayorista': (66,16),
 'precios_mercado_productores': (756,11),
 'dim_tiempo': (201,6), 'dim_cultivo': (5,6),
 'dim_ubicacion_produccion': (22,3), 'dim_region_costos': (25,2),
 'dim_pais_exportacion': (35,2), 'dim_mercado': (2,2),
 'fact_produccion_mensual': (561,10), 'fact_exportaciones_regionales': (720,5),
 'fact_exportaciones_danper': (495,4), 'fact_agroindustria_mensual': (3134,5),
 'fact_costos_mensuales': (6292,5), 'fact_abastecimiento_mayorista': (66,15),
 'fact_precios_mercado_productores': (756,10),
 'kpi_produccion_anual': (6,7), 'kpi_exportaciones_regionales_anual': (60,7),
 'kpi_exportaciones_danper_anual': (81,5), 'kpi_agroindustria_anual': (262,9),
 'kpi_costos_anual': (594,9), 'kpi_abastecimiento_anual': (6,11)
}
CROPS = ['ESPARRAGO','ALCACHOFA','ARANDANO','PALTA','UVA']


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check', action='store_true', help='Verificar HDFS sin escribir (predeterminado)')
    ap.add_argument('--build-missing', action='store_true', help='Crear SOLO componentes ausentes')
    ap.add_argument('--hdfs', default='hdfs://localhost:9000')
    ap.add_argument('--partitions', type=int, default=2)
    args = ap.parse_args()
    if args.check and args.build_missing:
        ap.error('Selecciona solo un modo')
    spark = (SparkSession.builder.appName('Danper_ETL_Gold')
             .master('local[2]')
             .config('spark.hadoop.fs.defaultFS', args.hdfs)
             .config('spark.sql.shuffle.partitions',str(args.partitions))
             .getOrCreate())
    spark.sparkContext.setLogLevel('ERROR')
    silver = args.hdfs.rstrip('/')+'/danper/silver'
    gold = args.hdfs.rstrip('/')+'/danper/gold'
    hconf = spark.sparkContext._jsc.hadoopConfiguration()
    Path = spark._jvm.org.apache.hadoop.fs.Path

    def exists(name):
        p=Path(f'{gold}/{name}')
        return p.getFileSystem(hconf).exists(p)

    def read(name):
        return spark.read.parquet(f'{gold}/{name}')

    def valid(name, df):
        rows,cols=EXPECTED[name]
        actual=df.count()
        if (actual,len(df.columns)) != (rows,cols):
            raise ValueError(f'{name}: esperado {(rows,cols)}, obtenido {(actual,len(df.columns))}')
        return df

    def publish(name, builder, keys=(), mandatory=()):
        if exists(name):
            df=valid(name,read(name))
            print(f'[EXISTENTE, VERIFICADO] {name} {EXPECTED[name]}',flush=True)
            return df
        df=valid(name,builder())
        if mandatory and df.filter(' OR '.join(f'`{x}` IS NULL' for x in mandatory)).limit(1).count():
            raise ValueError(f'{name}: clave obligatoria nula')
        if keys and df.groupBy(*keys).count().filter(F.col('count')>1).limit(1).count():
            raise ValueError(f'{name}: clave duplicada')
        df.coalesce(2 if EXPECTED[name][0]>5000 else 1).write.mode('errorifexists').parquet(f'{gold}/{name}')
        result=valid(name,read(name))
        print(f'[CREADO, VERIFICADO] {name} {EXPECTED[name]}',flush=True)
        return result

    def build_analytical():
        prod=spark.read.parquet(f'{silver}/produccion')
        vars={'Produccion (t.)':'produccion_t','Precio Chacra (S/Kg.)':'precio_chacra_s_kg',
              'Cosechas (ha.)':'cosechas_ha','Siembras (ha.)':'siembras_ha',
              'Sup.Verde (ha.)':'superficie_verde_ha','Sup Perdida (ha.)':'superficie_perdida_ha',
              'Rendimiento (Kg./ha.)':'rendimiento_kg_ha'}
        p=prod.withColumn('cultivo',F.upper(F.trim('cultivo'))).filter(F.col('cultivo').isin(CROPS)&F.col('periodo').isNotNull())
        result=p.groupBy('provincia','distrito','cultivo','periodo').pivot('variable',list(vars)).agg(F.first('valor',ignorenulls=True))
        for k,v in vars.items(): result=result.withColumnRenamed(k,v)
        return result.withColumn('anio',F.year('periodo')).withColumn('mes_numero',F.month('periodo'))

    def build_regional():
        df=spark.read.parquet(f'{silver}/exportaciones/regionales')
        df=df.withColumn('cultivo',F.upper(F.trim('cultivo'))).filter(F.col('cultivo').isin(CROPS)&F.col('anio').isNotNull()&F.col('numero_mes').between(1,12))
        pairs=((F.col('indicador')=='VOLUMEN')&(F.col('unidad')=='TONELADAS'))|((F.col('indicador')=='VALOR_FOB')&(F.col('unidad')=='MILES_USD'))|((F.col('indicador')=='PRECIO_FOB')&(F.col('unidad')=='USD_KG'))
        if df.filter(~pairs | F.col('indicador').isNull()).limit(1).count(): raise ValueError('Indicador/unidad regional incompatible')
        result=df.groupBy('cultivo','anio','numero_mes').pivot('indicador',['VOLUMEN','VALOR_FOB','PRECIO_FOB']).agg(F.first('valor',ignorenulls=True))
        return (result.withColumnRenamed('VOLUMEN','volumen_exportado_t')
                .withColumnRenamed('VALOR_FOB','valor_fob_miles_usd')
                .withColumnRenamed('PRECIO_FOB','precio_fob_usd_kg')
                .withColumn('periodo',F.make_date(F.col('anio').cast('int'),F.col('numero_mes').cast('int'),F.lit(1))))

    def build_danper():
        df=spark.read.parquet(f'{silver}/exportaciones/danper')
        if df.filter(F.col('periodo').isNull()|F.col('pais').isNull()|(F.trim('pais')=='')|F.col('fob_usd').isNull()|(F.col('fob_usd')<0)).limit(1).count(): raise ValueError('Exportacion Danper invalida')
        return (df.withColumn('pais',F.upper(F.trim('pais'))).groupBy('pais','periodo')
                .agg(F.sum('fob_usd').alias('valor_fob_usd'), F.count('*').alias('cantidad_registros_aduaneros'))
                .withColumn('anio',F.year('periodo')).withColumn('mes_numero',F.month('periodo')))

    def build_agro():
        df=(spark.read.parquet(f'{silver}/agroindustria')
            .withColumn('cultivo',F.upper(F.trim('cultivo')))
            .withColumn('proceso',F.upper(F.trim('proceso')))
            .withColumn('presentacion',F.upper(F.trim('presentacion')))
            .filter(F.col('cultivo').isin('ESPARRAGO','ALCACHOFA')))
        return (df.groupBy('cultivo','anio','numero_mes','proceso','presentacion')
                .agg(F.sum('cantidad_t').alias('cantidad_t'))
                .withColumn('periodo',F.make_date('anio','numero_mes',F.lit(1))))

    def build_costos():
        df=(spark.read.parquet(f'{silver}/costos').withColumn('region',F.upper(F.trim('region')))
            .withColumn('tipo_costo',F.upper(F.trim('tipo_costo')))
            .withColumn('unidad',F.upper(F.trim('unidad'))))
        return (df.select('region','tipo_costo','anio','numero_mes',F.col('valor').alias('valor_costo'),'unidad')
                .withColumn('periodo',F.make_date('anio','numero_mes',F.lit(1))))

    def build_abast():
        df=spark.read.parquet(f'{silver}/abastecimiento')
        df=(df.withColumn('mercado',F.upper(F.trim('mercado')))
            .withColumn('producto',F.upper(F.trim('producto')))
            .withColumn('unidad_medida',F.upper(F.trim('unidad_medida')))
            .withColumn('fecha',F.to_date('fecha_reporte','yyyy-MM-dd')))
        return (df.select('mercado','producto',F.col('fecha').alias('fecha_reporte'),
                'unidad_medida','equivalencia_kg','ingreso_ayer_t','ingreso_hoy_t',
                'promedio_ingreso_7dias_t','promedio_ingreso_4semanas_t',
                'precio_ayer_soles','precio_hoy_soles','precio_7dias_soles','tendencia')
                .withColumn('tiene_dato_ingreso',F.col('ingreso_hoy_t').isNotNull())
                .withColumn('anio',F.year('fecha_reporte')).withColumn('mes_numero',F.month('fecha_reporte')))

    def build_market():
        df=(spark.read.parquet(f'{silver}/mercado_productores')
            .withColumn('mercado',F.upper(F.trim('mercado')))
            .withColumn('categoria',F.upper(F.trim('categoria')))
            .withColumn('producto',F.upper(F.trim('producto')))
            .withColumn('unidad_medida',F.upper(F.trim('unidad_medida'))))
        return (df.select('mercado','categoria','producto','unidad_medida','fecha_reporte',
                'precio_ayer_soles','precio_hoy_soles','precio_7dias_soles','variacion_porcentaje')
                .withColumn('anio',F.year('fecha_reporte')).withColumn('mes_numero',F.month('fecha_reporte')))

    builders_analytical=[build_analytical,build_regional,build_danper,build_agro,build_costos,build_abast,build_market]
    names_analytical=list(EXPECTED)[:7]

    def dimensions(tables):
        periods=[]
        for df in tables.values():
            field='periodo' if 'periodo' in df.columns else 'fecha_reporte'
            periods.append(df.select(F.trunc(field,'month').alias('periodo')))
        all_periods=periods[0]
        for p in periods[1:]: all_periods=all_periods.unionByName(p)
        dt=(all_periods.filter(F.col('periodo').isNotNull()).distinct()
            .withColumn('anio',F.year('periodo')).withColumn('mes_numero',F.month('periodo'))
            .withColumn('trimestre',F.quarter('periodo'))
            .withColumn('tiempo_id',F.year('periodo')*100+F.month('periodo'))
            .withColumn('anio_mes',F.date_format('periodo','yyyy-MM'))
            .select('tiempo_id','periodo','anio','trimestre','mes_numero','anio_mes'))
        def fieldcrop(name,column): return tables[name].select(F.upper(F.trim(column)).alias('cultivo')).distinct()
        sources=[('produccion_mensual','cultivo','tiene_produccion'),('exportaciones_regionales','cultivo','tiene_exportaciones_regionales'),
                 ('agroindustria_mensual','cultivo','tiene_agroindustria'),('abastecimiento_mayorista','producto','tiene_abastecimiento')]
        crops=[fieldcrop(n,c).withColumn(flag,F.lit(True)) for n,c,flag in sources]
        names=crops[0].select('cultivo')
        for c in crops[1:]: names=names.unionByName(c.select('cultivo'))
        names=names.filter(F.col('cultivo').isNotNull()&(F.col('cultivo')!='')).distinct()
        for c in crops: names=names.join(c,'cultivo','left')
        flags=[f for _,_,f in sources]
        dc=(names.fillna({f:False for f in flags}).withColumn('cultivo_id',F.row_number().over(Window.orderBy('cultivo')))
            .select('cultivo_id','cultivo',*flags))
        def enumerated(df,keys,idcol):
            return (df.distinct().withColumn(idcol,F.row_number().over(Window.orderBy(*keys))).select(idcol,*keys))
        loc=enumerated(tables['produccion_mensual'].select(F.upper(F.trim('provincia')).alias('provincia'),F.upper(F.trim('distrito')).alias('distrito')),['provincia','distrito'],'ubicacion_produccion_id')
        regions=enumerated(tables['costos_mensuales'].select(F.upper(F.trim('region')).alias('region')),['region'],'region_id')
        countries=enumerated(tables['exportaciones_danper'].select(F.upper(F.trim('pais')).alias('pais')),['pais'],'pais_id')
        markets=enumerated(tables['abastecimiento_mayorista'].select(F.upper(F.trim('mercado')).alias('mercado')).unionByName(
            tables['precios_mercado_productores'].select(F.upper(F.trim('mercado')).alias('mercado'))),['mercado'],'mercado_id')
        return [dt,dc,loc,regions,countries,markets]

    def facts(t,d):
        time,crop,loc,reg,pais,merc=d
        prod=(t['produccion_mensual'].alias('p')
              .join(time.select('periodo','tiempo_id').alias('tt'),F.col('p.periodo')==F.col('tt.periodo'),'left')
              .join(crop.select('cultivo','cultivo_id').alias('cc'),F.col('p.cultivo')==F.col('cc.cultivo'),'left')
              .join(loc.alias('ll'),(F.col('p.provincia')==F.col('ll.provincia'))&(F.col('p.distrito')==F.col('ll.distrito')),'left')
              .select(F.col('tt.tiempo_id'),F.col('cc.cultivo_id'),F.col('ll.ubicacion_produccion_id'),
                      *[F.col('p.'+c) for c in ('produccion_t','precio_chacra_s_kg','cosechas_ha','siembras_ha','superficie_verde_ha','superficie_perdida_ha','rendimiento_kg_ha')]))
        exp=(t['exportaciones_regionales'].alias('e')
             .join(time.select('periodo','tiempo_id').alias('tt'),F.col('e.periodo')==F.col('tt.periodo'),'left')
             .join(crop.select('cultivo','cultivo_id').alias('cc'),F.col('e.cultivo')==F.col('cc.cultivo'),'left')
             .select('tiempo_id','cultivo_id',*[F.col('e.'+c) for c in ('volumen_exportado_t','valor_fob_miles_usd','precio_fob_usd_kg')]))
        dep=(t['exportaciones_danper'].alias('e')
             .join(time.select('periodo','tiempo_id').alias('tt'),F.col('e.periodo')==F.col('tt.periodo'),'left')
             .join(pais.select('pais','pais_id').alias('pp'),F.col('e.pais')==F.col('pp.pais'),'left')
             .select('tiempo_id','pais_id',F.col('e.valor_fob_usd'),F.col('e.cantidad_registros_aduaneros')))
        agro=(t['agroindustria_mensual'].alias('a')
              .join(time.select('periodo','tiempo_id').alias('tt'),F.col('a.periodo')==F.col('tt.periodo'),'left')
              .join(crop.select('cultivo','cultivo_id').alias('cc'),F.col('a.cultivo')==F.col('cc.cultivo'),'left')
              .select('tiempo_id','cultivo_id',F.col('a.proceso'),F.col('a.presentacion'),F.col('a.cantidad_t')))
        cost=(t['costos_mensuales'].alias('c')
              .join(time.select('periodo','tiempo_id').alias('tt'),F.col('c.periodo')==F.col('tt.periodo'),'left')
              .join(reg.select('region','region_id').alias('rr'),F.col('c.region')==F.col('rr.region'),'left')
              .select('tiempo_id','region_id',F.col('c.tipo_costo'),F.col('c.valor_costo'),F.col('c.unidad')))
        ab=(t['abastecimiento_mayorista'].alias('a')
            .join(time.select('periodo','tiempo_id').alias('tt'),F.trunc('a.fecha_reporte','month')==F.col('tt.periodo'),'left')
            .join(crop.select('cultivo','cultivo_id').alias('cc'),F.col('a.producto')==F.col('cc.cultivo'),'left')
            .join(merc.select('mercado','mercado_id').alias('mm'),F.col('a.mercado')==F.col('mm.mercado'),'left')
            .select('tiempo_id','cultivo_id','mercado_id',*[F.col('a.'+c) for c in (
                'fecha_reporte','unidad_medida','equivalencia_kg','ingreso_ayer_t','ingreso_hoy_t',
                'promedio_ingreso_7dias_t','promedio_ingreso_4semanas_t','precio_ayer_soles','precio_hoy_soles',
                'precio_7dias_soles','tendencia','tiene_dato_ingreso')]))
        mk=(t['precios_mercado_productores'].alias('p')
            .join(time.select('periodo','tiempo_id').alias('tt'),F.trunc('p.fecha_reporte','month')==F.col('tt.periodo'),'left')
            .join(merc.select('mercado','mercado_id').alias('mm'),F.col('p.mercado')==F.col('mm.mercado'),'left')
            .select('tiempo_id','mercado_id',*[F.col('p.'+c) for c in (
                'fecha_reporte','categoria','producto','unidad_medida','precio_ayer_soles','precio_hoy_soles','precio_7dias_soles','variacion_porcentaje')]))
        return [prod,exp,dep,agro,cost,ab,mk]

    def kpis(facts,dims):
        time,crop,_,reg,pais,merc=dims
        prod,regional,danper,agro,cost,ab,_=facts
        ti=time.select('tiempo_id','anio'); cu=crop.select('cultivo_id','cultivo')
        pr=(prod.join(cu,'cultivo_id').join(ti,'tiempo_id').groupBy('cultivo','anio')
            .agg(F.sum('produccion_t').alias('produccion_reportada_t'),F.avg('precio_chacra_s_kg').alias('precio_promedio_chacra_s_kg'),
                 F.count('*').alias('registros_total'),F.count('produccion_t').alias('registros_con_produccion'),
                 F.count('precio_chacra_s_kg').alias('registros_con_precio')))
        ex=(regional.join(cu,'cultivo_id').join(ti,'tiempo_id').groupBy('cultivo','anio')
            .agg(F.sum('volumen_exportado_t').alias('volumen_exportado_reportado_t'),
                 F.sum('valor_fob_miles_usd').alias('valor_fob_reportado_miles_usd'),F.count('*').alias('registros_total'),
                 F.count('volumen_exportado_t').alias('registros_con_volumen'),F.count('valor_fob_miles_usd').alias('registros_con_valor_fob')))
        de=(danper.join(pais.select('pais_id','pais'),'pais_id').join(ti,'tiempo_id').groupBy('pais','anio')
            .agg(F.sum('valor_fob_usd').alias('valor_fob_reportado_usd'),
                 F.sum('cantidad_registros_aduaneros').alias('cantidad_registros_aduaneros'),F.count('*').alias('registros_total')))
        ag=(agro.join(cu,'cultivo_id').join(ti,'tiempo_id').groupBy('cultivo','anio','proceso','presentacion')
            .agg(F.sum('cantidad_t').alias('cantidad_reportada_t'),F.count('*').alias('registros_total'),
                 F.count('cantidad_t').alias('registros_con_cantidad'),F.sum(F.when(F.col('cantidad_t')==0,1).otherwise(0)).alias('registros_cantidad_cero'),
                 F.sum(F.when(F.col('cantidad_t')>0,1).otherwise(0)).alias('registros_cantidad_positiva')))
        co=(cost.join(reg.select('region_id','region'),'region_id').join(ti,'tiempo_id')
            .groupBy('region','anio','tipo_costo','unidad')
            .agg(F.avg('valor_costo').alias('valor_promedio_reportado'),F.min('valor_costo').alias('valor_minimo_reportado'),
                 F.max('valor_costo').alias('valor_maximo_reportado'),F.count('*').alias('registros_total'),F.count('valor_costo').alias('registros_con_valor')))
        abb=(ab.join(cu,'cultivo_id').join(ti,'tiempo_id').join(merc.select('mercado_id','mercado'),'mercado_id')
             .groupBy('cultivo','mercado','anio','unidad_medida','equivalencia_kg')
             .agg(F.avg('ingreso_hoy_t').alias('ingreso_promedio_reportado_t'),F.avg('precio_hoy_soles').alias('precio_promedio_reportado_soles'),
                  F.count('*').alias('reportes_total'),F.count('ingreso_hoy_t').alias('reportes_con_ingreso'),F.count('precio_hoy_soles').alias('reportes_con_precio'))
             .withColumn('cobertura_ingreso_pct',F.round(F.col('reportes_con_ingreso')/F.col('reportes_total')*100,2)))
        return [pr,ex,de,ag,co,abb]

    try:
        if not args.build_missing:
            print('MODO SEGURO --check: ninguna escritura HDFS',flush=True)
            bad=[]
            for i,(name,(rows,cols)) in enumerate(EXPECTED.items(),1):
                if not exists(name):
                    print(f'[{i:02d}/26] AUSENTE {name}',flush=True); bad.append(name); continue
                try: valid(name,read(name)); print(f'[{i:02d}/26] OK {name}: {rows} filas, {cols} columnas',flush=True)
                except Exception as exc: print(f'[{i:02d}/26] ERROR {name}: {exc}',flush=True); bad.append(name)
            if bad: raise RuntimeError(f'{len(bad)} componentes requieren revision: {bad}')
            print('AUDITORIA GOLD: 26/26 CORRECTOS. HDFS NO MODIFICADO.')
            return
        print('MODO --build-missing: solo rutas ausentes, NUNCA sobrescribe',flush=True)
        tables={name:publish(name,builder) for name,builder in zip(names_analytical,builders_analytical)}
        dim_names=list(EXPECTED)[7:13]
        if all(exists(n) for n in dim_names):
            dims=[publish(n,lambda:None) for n in dim_names]
        else:
            ds=dimensions(tables)
            dimkeys=[['tiempo_id'],['cultivo_id'],['ubicacion_produccion_id'],['region_id'],['pais_id'],['mercado_id']]
            dims=[publish(n,lambda df=df:df,keys=k,mandatory=k) for n,df,k in zip(dim_names,ds,dimkeys)]
        fact_names=list(EXPECTED)[13:20]
        if all(exists(n) for n in fact_names):
            fs=[publish(n,lambda:None) for n in fact_names]
        else:
            generated=facts(tables,dims)
            fk=[['tiempo_id','cultivo_id','ubicacion_produccion_id'],['tiempo_id','cultivo_id'],['tiempo_id','pais_id'],
                ['tiempo_id','cultivo_id'],['tiempo_id','region_id'],['tiempo_id','cultivo_id','mercado_id'],['tiempo_id','mercado_id']]
            natural=[fk[0],fk[1],fk[2],fk[3]+['proceso','presentacion'],fk[4]+['tipo_costo'],
                     ['fecha_reporte','cultivo_id','mercado_id'],['mercado_id','fecha_reporte','categoria','producto','unidad_medida']]
            fs=[publish(n,lambda df=df:df,keys=key,mandatory=foreign) for n,df,key,foreign in zip(fact_names,generated,natural,fk)]
        kpi_names=list(EXPECTED)[20:]
        if all(exists(n) for n in kpi_names):
            ks=[publish(n,lambda:None) for n in kpi_names]
        else:
            generated=kpis(fs,dims)
            keys=[['cultivo','anio'],['cultivo','anio'],['pais','anio'],['cultivo','anio','proceso','presentacion'],
                  ['region','anio','tipo_costo','unidad'],['cultivo','mercado','anio','unidad_medida','equivalencia_kg']]
            ks=[publish(n,lambda df=df:df,keys=k,mandatory=k) for n,df,k in zip(kpi_names,generated,keys)]
        print('PROCESAMIENTO GOLD: 26 COMPONENTES VERIFICADOS')
    finally:
        spark.stop()

if __name__=='__main__':
    main()
