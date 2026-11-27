#!/usr/bin/env bash
# Ingesta automática en el master: S3 -> datasets locales -> pipeline completo.
#
# Cada INTERVALO segundos copia de s3://<bucket>/datasets/ los archivos nuevos
# (sincronizar_datasets.sh) y run_pipeline.py --vigilar los lleva por Bronze,
# Silver, Gold, el modelo (aplicar) y PostgreSQL. Basta con subir un archivo
# al bucket desde la consola de AWS: no hay que entrar al master.
#
# Normalmente no se ejecuta a mano: lo arranca el servicio danper-ingesta
# (infra/aws/activar_ingesta.sh). Para probarlo a mano, como usuario danper:
#   bash infra/aws/ingesta_continua.sh
set -uo pipefail

INTERVALO=${DANPER_INTERVALO_INGESTA:-60}
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
export PATH=$PATH:/opt/hadoop/bin:/opt/spark/bin:/snap/bin:/usr/local/bin
PYTHON=${PYSPARK_PYTHON:-python3}
cd "$REPO"

# Variables de RDS y del bucket, leídas de Parameter Store con el rol del master
source infra/aws/entorno_aws.sh || exit 1

# Sincronización con S3 en segundo plano
(
    while true; do
        bash infra/aws/sincronizar_datasets.sh || echo "Aviso: falló la sincronización con S3"
        sleep "$INTERVALO"
    done
) &

# El pipeline vigila la carpeta local y procesa lo nuevo
exec "$PYTHON" scripts/run_pipeline.py --vigilar "$INTERVALO"
