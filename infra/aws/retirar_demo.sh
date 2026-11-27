#!/usr/bin/env bash
# Retira los datos de prueba (Excel "DEMO" de ingreso a planta) y deja la
# plataforma como antes de la demostración.
#
# Uso (en el master, con sudo):
#   1. En la consola de AWS, borrar de s3://<bucket>/datasets/agroindustria/ los
#      archivos que contienen "DEMO" (el rol del master no puede borrar en S3).
#   2. sudo bash infra/aws/retirar_demo.sh
#
# Qué hace: detiene danper-ingesta, borra los DEMO de la carpeta local y de
# Bronze, los quita de la tabla de control, recalcula Silver de agroindustria,
# Gold, el modelo (aplicar, sin reentrenar) y la publicación en RDS, y vuelve a
# arrancar el servicio. Tarda unos 4 minutos.
set -euo pipefail

[[ $EUID -eq 0 ]] || { echo "ERROR: ejecutar con sudo" >&2; exit 1; }
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)

# bash -l carga /etc/profile.d/danper.sh (variables y PATH de Hadoop y Spark)
como_danper() { sudo -u danper -H bash -lc "$1"; }

echo "==> Comprobando que ya no hay DEMO en S3"
QUEDAN=$(como_danper "source $REPO/infra/aws/entorno_aws.sh >/dev/null && \
    aws s3 ls s3://\$DANPER_BUCKET/datasets/agroindustria/ | grep -c DEMO || true")
if [[ $QUEDAN != 0 ]]; then
    echo "ERROR: todavía hay $QUEDAN archivo(s) DEMO en S3. Bórralos primero en la consola." >&2
    exit 1
fi

echo "==> Deteniendo danper-ingesta"
systemctl stop danper-ingesta

trap 'echo "==> Arrancando danper-ingesta"; systemctl start danper-ingesta' EXIT

echo "==> Borrando los DEMO de la carpeta local, de Bronze y de la tabla de control"
como_danper "set -e
    rm -fv \"\$DANPER_DATASETS\"/agroindustria/*DEMO* 2>/dev/null || true
    hdfs dfs -rm -f '/danper/bronze/agroindustria/*DEMO*' || true
    hdfs dfs -cat /danper/control/archivos.csv | grep -v DEMO > /tmp/archivos.csv
    hdfs dfs -put -f /tmp/archivos.csv /danper/control/archivos.csv
    echo \"Filas DEMO en la tabla de control: \$(hdfs dfs -cat /danper/control/archivos.csv | grep -c DEMO || true)\""

echo "==> Recalculando Silver, Gold, modelo y RDS (unos 4 minutos)"
como_danper "set -eo pipefail
    source $REPO/infra/aws/entorno_aws.sh >/dev/null
    cd $REPO/scripts
    python transformacion_agroindustria_silver.py 2>&1 | grep 'Registros guardados'
    spark-submit procesamiento_gold.py --rebuild 2>&1 | grep -E 'REEMPLAZADO|VERIFICADOS'
    spark-submit modelo_abastecimiento.py --aplicar 2>&1 | grep -E '^Plan|Modelo aplicado'
    python publicar_postgres.py 2>&1 | grep -E 'Auditoría|PUBLICACION'"

# El portal deja de mostrar las cargas de prueba
como_danper "rm -f \"\$DANPER_ESTADO/cargas.json\""
echo "Listo: datos de prueba retirados."
