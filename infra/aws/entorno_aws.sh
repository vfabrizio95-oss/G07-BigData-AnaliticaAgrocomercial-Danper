#!/usr/bin/env bash
# Carga en la sesión las variables para usar RDS y S3 desde el master.
# Las contraseñas se leen de Parameter Store con el rol de la máquina: no se
# guardan en ningún archivo ni en el historial de la terminal.
#
# Uso (en el master, como usuario danper; "source" o "." para que las
# variables queden en la sesión actual):
#
#   source infra/aws/entorno_aws.sh
#   python scripts/publicar_postgres.py
#
# Parámetros que lee (se crean en la consola: Systems Manager > Parameter Store):
#   /danper/rds/endpoint          String        endpoint de RDS (sin puerto)
#   /danper/s3/bucket             String        nombre del bucket
#   /danper/etl_escritor/clave    SecureString  contraseña de etl_escritor
#
# Variables que deja definidas:
#   DANPER_PG_URL       jdbc:postgresql://<endpoint>:5432/danper?sslmode=require
#   DANPER_PG_USER      etl_escritor
#   DANPER_PG_PASSWORD  (desde Parameter Store)
#   DANPER_BUCKET       nombre del bucket
#   AWS_DEFAULT_REGION  región de la máquina

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
    echo "Usar con source: source ${BASH_SOURCE[0]}" >&2
    exit 1
fi

_danper_cargar() {
    local token region
    if ! command -v aws >/dev/null; then
        echo "ERROR: falta AWS CLI. Instalar una vez con: sudo snap install aws-cli --classic" >&2
        return 1
    fi

    # Región de la máquina (servicio de metadatos de EC2, IMDSv2)
    if [[ -z ${AWS_DEFAULT_REGION:-} ]]; then
        token=$(curl -sf -m 2 -X PUT http://169.254.169.254/latest/api/token \
                -H "X-aws-ec2-metadata-token-ttl-seconds: 60")
        region=$(curl -sf -m 2 -H "X-aws-ec2-metadata-token: $token" \
                http://169.254.169.254/latest/meta-data/placement/region)
        export AWS_DEFAULT_REGION=${region:-us-east-1}
    fi

    _parametro() {  # _parametro NOMBRE -> valor (descifrado si es SecureString)
        aws ssm get-parameter --name "$1" --with-decryption \
            --query Parameter.Value --output text
    }

    local endpoint bucket clave
    endpoint=$(_parametro /danper/rds/endpoint) || return 1
    bucket=$(_parametro /danper/s3/bucket) || return 1
    clave=$(_parametro /danper/etl_escritor/clave) || return 1

    export DANPER_PG_URL="jdbc:postgresql://$endpoint:${DANPER_PG_PORT:-5432}/danper?sslmode=require"
    export DANPER_PG_USER=etl_escritor
    export DANPER_PG_PASSWORD=$clave
    export DANPER_BUCKET=$bucket

    echo "Entorno AWS cargado:"
    echo "  región     $AWS_DEFAULT_REGION"
    echo "  PostgreSQL $DANPER_PG_URL (usuario $DANPER_PG_USER)"
    echo "  bucket     s3://$DANPER_BUCKET"
    echo "  HDFS       ${DANPER_HDFS_URI:-sin definir}"
}

_danper_cargar
unset -f _danper_cargar _parametro
