#!/usr/bin/env bash
# Copia los datasets del bucket (s3://<bucket>/datasets/) a la carpeta que lee
# el pipeline en el master (DANPER_DATASETS, por defecto /opt/danper/datasets).
#
# Uso (en el master, como usuario danper):
#   source infra/aws/entorno_aws.sh
#   bash infra/aws/sincronizar_datasets.sh
#   python scripts/run_pipeline.py          # Bronze -> Silver -> Gold -> PostgreSQL
#
# Solo descarga archivos nuevos o cambiados y nunca borra nada en local: un
# PDF nuevo del GMML subido a s3://<bucket>/datasets/abastecimiento/... llega
# a la carpeta y el pipeline (o run_pipeline.py --vigilar) lo procesa.
# Para vigilar S3 de forma continua:
#   while true; do bash infra/aws/sincronizar_datasets.sh; sleep 60; done
set -euo pipefail

: "${DANPER_BUCKET:?falta DANPER_BUCKET: ejecutar antes 'source infra/aws/entorno_aws.sh'}"
DESTINO=${DANPER_DATASETS:-/opt/danper/datasets}

mkdir -p "$DESTINO"
antes=$(find "$DESTINO" -type f | wc -l)
aws s3 sync "s3://$DANPER_BUCKET/datasets/" "$DESTINO/" --only-show-errors
despues=$(find "$DESTINO" -type f | wc -l)
echo "$(date '+%F %T') datasets: $despues archivos en $DESTINO ($((despues - antes)) nuevos)"
