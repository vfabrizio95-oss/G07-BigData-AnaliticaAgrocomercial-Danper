#!/usr/bin/env bash
# Levanta el tablero de Grafana en el master, conectado a RDS con el usuario de
# solo lectura grafana_lector y conexión cifrada (SSL).
#
# Uso (en el master, con sudo):
#   sudo bash infra/aws/iniciar_grafana.sh          # levantar o actualizar
#   sudo bash infra/aws/iniciar_grafana.sh --parar  # detener
#
# Grafana escucha solo en 127.0.0.1:3000 del master: no se abre ningún puerto.
# Con el portal público (instalar_portal.sh), nginx lo publica por CloudFront.
# Para verlo desde tu PC, abre un túnel de Session Manager (AWS CLI y el
# plugin de Session Manager instalados en tu PC):
#   aws ssm start-session --target <id-instancia-master> \
#       --document-name AWS-StartPortForwardingSession \
#       --parameters portNumber=3000,localPortNumber=3000
# y entra a http://localhost:3000
#
# Parámetros de Parameter Store que usa:
#   /danper/rds/endpoint          String        endpoint de RDS
#   /danper/grafana_lector/clave  SecureString  contraseña de grafana_lector
#   /danper/grafana/admin_clave   SecureString  contraseña del usuario admin de Grafana
set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
COMPOSE="$REPO/dashboard/docker-compose.yml"
[[ -f $COMPOSE ]] || { echo "ERROR: no se encuentra $COMPOSE" >&2; exit 1; }
[[ $EUID -eq 0 ]] || { echo "ERROR: ejecutar con sudo" >&2; exit 1; }

if [[ ${1:-} == --parar ]]; then
    docker compose -f "$COMPOSE" down
    exit 0
fi

# Docker y AWS CLI (solo si faltan)
if ! command -v docker >/dev/null || ! docker compose version >/dev/null 2>&1; then
    apt-get update -q
    apt-get install -y -q docker.io docker-compose-v2
    systemctl enable --now docker
fi
if ! command -v aws >/dev/null; then
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

# docker compose toma estas variables del entorno (no se escribe ningún .env)
export DANPER_GRAFANA_PG_HOST="$(parametro /danper/rds/endpoint):${DANPER_PG_PORT:-5432}"
export DANPER_GRAFANA_PG_PASSWORD="$(parametro /danper/grafana_lector/clave)"
export DANPER_GRAFANA_ADMIN_PASSWORD="$(parametro /danper/grafana/admin_clave)"
# Grafana interpreta "$" dentro de los valores de provisioning (aunque se
# escriba "$$"), así que una contraseña con "$" nunca llega bien a la base.
if [[ $DANPER_GRAFANA_PG_PASSWORD == *'$'* ]]; then
    echo "ERROR: la contraseña /danper/grafana_lector/clave contiene '\$', que Grafana no admite." >&2
    echo "Cambiarla en Parameter Store y volver a ejecutar preparar_rds.sh y este script." >&2
    exit 1
fi
export DANPER_GRAFANA_PG_SSLMODE=require
export DANPER_GRAFANA_ADDR=127.0.0.1
# Portal público (lo crea infra/aws/instalar_portal.sh): tablero anónimo de
# solo lectura detrás de nginx y CloudFront, con su URL pública.
if [[ -f /etc/danper/portal.conf ]]; then
    # shellcheck disable=SC1091
    . /etc/danper/portal.conf
    export DANPER_GRAFANA_ANONIMO=true
    export DANPER_GRAFANA_ROOT_URL=${DOMINIO_PUBLICO:+https://$DOMINIO_PUBLICO/}
    echo "Modo público: tablero anónimo de solo lectura (${DOMINIO_PUBLICO:-dominio aún no definido})"
fi

docker compose -f "$COMPOSE" up -d --force-recreate

# La primera vez Grafana prepara su base interna: puede tardar unos minutos
echo "Esperando a Grafana (la primera vez puede tardar hasta 5 minutos) ..."
for _ in $(seq 1 150); do
    curl -sf -m 2 http://127.0.0.1:3000/api/health >/dev/null && break
    sleep 2
done

# Comprobar la fuente de datos (consulta real a RDS con grafana_lector)
ESTADO=$(curl -sf -m 15 -u "admin:$DANPER_GRAFANA_ADMIN_PASSWORD" \
         http://127.0.0.1:3000/api/datasources/uid/danper-gold/health || true)
unset DANPER_GRAFANA_PG_PASSWORD DANPER_GRAFANA_ADMIN_PASSWORD
echo "Fuente de datos Danper Gold: ${ESTADO:-sin respuesta}"
if [[ $ESTADO != *'"status":"OK"'* ]]; then
    echo "ERROR: Grafana no pudo consultar RDS. Revisar: docker logs danper-grafana" >&2
    exit 1
fi
echo "Listo: Grafana en 127.0.0.1:3000 del master (entrar por el túnel de Session Manager)."
