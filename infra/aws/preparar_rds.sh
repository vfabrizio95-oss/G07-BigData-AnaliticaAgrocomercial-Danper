#!/usr/bin/env bash
# Prepara la base de datos de RDS una sola vez: crea los roles etl_escritor y
# grafana_lector y los esquemas gold y gold_staging (infra/aws/sql/roles_postgres.sql).
#
# Uso (en el master, con sudo):
#   sudo bash infra/aws/preparar_rds.sh
#
# Parámetros de Parameter Store que usa (además de los de entorno_aws.sh):
#   /danper/rds/admin_usuario     String        usuario administrador de RDS
#   /danper/rds/admin_clave       SecureString  su contraseña
#   /danper/etl_escritor/clave    SecureString  contraseña que tendrá etl_escritor
#   /danper/grafana_lector/clave  SecureString  contraseña que tendrá grafana_lector
#
# La conexión usa SSL (sslmode=require). Se puede volver a ejecutar: vuelve a
# fijar las contraseñas con los valores actuales de Parameter Store.
set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
SQL="$REPO/infra/aws/sql/roles_postgres.sql"
[[ -f $SQL ]] || { echo "ERROR: no se encuentra $SQL" >&2; exit 1; }

# Herramientas: cliente de PostgreSQL 16 y AWS CLI (solo si faltan)
if ! command -v psql >/dev/null; then
    [[ $EUID -eq 0 ]] || { echo "ERROR: falta psql; ejecutar con sudo" >&2; exit 1; }
    apt-get update -q && apt-get install -y -q postgresql-client-16
fi
if ! command -v aws >/dev/null; then
    [[ $EUID -eq 0 ]] || { echo "ERROR: falta AWS CLI; ejecutar con sudo" >&2; exit 1; }
    snap install aws-cli --classic
    hash -r
fi

if [[ -z ${AWS_DEFAULT_REGION:-} ]]; then
    TOKEN=$(curl -sf -m 2 -X PUT http://169.254.169.254/latest/api/token \
            -H "X-aws-ec2-metadata-token-ttl-seconds: 60" || true)
    REGION=$(curl -sf -m 2 -H "X-aws-ec2-metadata-token: $TOKEN" \
            http://169.254.169.254/latest/meta-data/placement/region || true)
    export AWS_DEFAULT_REGION=${REGION:-us-east-2}
fi

parametro() {
    aws ssm get-parameter --name "$1" --with-decryption --query Parameter.Value --output text
}

ENDPOINT=$(parametro /danper/rds/endpoint)
ADMIN=$(parametro /danper/rds/admin_usuario)
# psql lee la contraseña de PGPASSWORD: no aparece en la lista de procesos
PGPASSWORD=$(parametro /danper/rds/admin_clave)
CLAVE_ETL=$(parametro /danper/etl_escritor/clave)
CLAVE_GRAFANA=$(parametro /danper/grafana_lector/clave)
export PGPASSWORD

echo "Conectando a $ENDPOINT como $ADMIN ..."
psql "host=$ENDPOINT port=${DANPER_PG_PORT:-5432} dbname=danper user=$ADMIN sslmode=require connect_timeout=10" \
     -v clave_etl="$CLAVE_ETL" -v clave_grafana="$CLAVE_GRAFANA" -f "$SQL"
unset PGPASSWORD CLAVE_ETL CLAVE_GRAFANA

echo
echo "Listo. Comprobación con cada usuario:"
for usuario in etl_escritor grafana_lector; do
    clave=$(parametro "/danper/$usuario/clave")
    if PGPASSWORD=$clave psql "host=$ENDPOINT port=${DANPER_PG_PORT:-5432} dbname=danper user=$usuario sslmode=require connect_timeout=10" \
            -qAt -c "SELECT '  ' || current_user || ': conexión SSL ' || CASE WHEN ssl THEN 'sí' ELSE 'no' END FROM pg_stat_ssl WHERE pid = pg_backend_pid()"; then
        :
    else
        echo "  $usuario: NO se pudo conectar" >&2
        exit 1
    fi
done
