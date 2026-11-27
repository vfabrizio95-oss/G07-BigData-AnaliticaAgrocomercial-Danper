#!/usr/bin/env bash
# Publica la plataforma en una URL fija: nginx + portal web + Grafana público.
#
#   https://<distribucion>.cloudfront.net/          tablero de Grafana (solo lectura)
#   https://<distribucion>.cloudfront.net/carga     carga de datos (con contraseña)
#   https://<distribucion>.cloudfront.net/estado    avance del pipeline
#
# Uso (en el master, con sudo; se puede repetir):
#   sudo bash infra/aws/instalar_portal.sh                        # primera vez
#   sudo bash infra/aws/instalar_portal.sh --dominio dxxxx.cloudfront.net
#                                    # una vez creada la distribución de CloudFront
#
# Antes, en la consola de AWS (ver docs/despliegue_aws.md):
#   - Parameter Store: /danper/portal/clave (SecureString), contraseña de /carga.
#   - Rol del master: política infra/aws/iam/politica_master.json actualizada
#     (s3:PutObject en datasets/).
#   - IP elástica en el master y grupo de seguridad danper-web (puerto 80 solo
#     desde la lista de prefijos de CloudFront).
#
# Qué hace:
#   1. Instala nginx y las dependencias del portal (web/requirements.txt).
#   2. Crea /opt/danper/estado (avance del pipeline) y lo agrega al entorno.
#   3. Genera el secreto del encabezado X-Danper-Origen (una sola vez) y
#      configura nginx: sin ese encabezado, que solo agrega CloudFront, responde 403.
#   4. Crea el servicio danper-portal (gunicorn en 127.0.0.1:8000).
#   5. Pasa Grafana a modo público de solo lectura (iniciar_grafana.sh).
set -euo pipefail

[[ $EUID -eq 0 ]] || { echo "ERROR: ejecutar con sudo" >&2; exit 1; }
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
ENTORNO=/etc/danper/entorno
CONF=/etc/danper/portal.conf
SECRETO=/etc/danper/origen_cloudfront
USUARIO=danper
VENV=/opt/danper/.venv
ESTADO=/opt/danper/estado
[[ -f $ENTORNO ]] || { echo "ERROR: falta $ENTORNO; ¿se ejecutó instalar_nodo.sh?" >&2; exit 1; }

DOMINIO=""
if [[ ${1:-} == --dominio ]]; then
    DOMINIO=${2:?falta el dominio, por ejemplo dxxxx.cloudfront.net}
    DOMINIO=${DOMINIO#https://}; DOMINIO=${DOMINIO%/}
fi
paso() { printf '\n==> %s\n' "$*"; }

paso "1/5 nginx y dependencias del portal"
command -v nginx >/dev/null || { apt-get update -q; apt-get install -y -q nginx; }
sudo -u "$USUARIO" "$VENV/bin/pip" install -q -r "$REPO/web/requirements.txt"

paso "2/5 Carpeta de estado del pipeline"
install -d -o "$USUARIO" -g "$USUARIO" "$ESTADO"
grep -q '^DANPER_ESTADO=' "$ENTORNO" || echo "DANPER_ESTADO=$ESTADO" >> "$ENTORNO"
TOKEN=$(curl -sf -m 2 -X PUT http://169.254.169.254/latest/api/token \
        -H "X-aws-ec2-metadata-token-ttl-seconds: 60" || true)
REGION=$(curl -sf -m 2 -H "X-aws-ec2-metadata-token: $TOKEN" \
         http://169.254.169.254/latest/meta-data/placement/region || true)
REGION=${REGION:-us-east-2}

paso "3/5 nginx con el encabezado secreto de CloudFront"
if [[ ! -s $SECRETO ]]; then
    (umask 077; head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' > "$SECRETO")
fi
VALOR=$(cat "$SECRETO")
sed "s/SECRETO_ORIGEN/$VALOR/g" "$REPO/infra/aws/conf/nginx-danper.conf" \
    > /etc/nginx/sites-available/danper
chmod 640 /etc/nginx/sites-available/danper
ln -sf /etc/nginx/sites-available/danper /etc/nginx/sites-enabled/danper
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable --now nginx
systemctl reload nginx

paso "4/5 Servicio danper-portal"
cat > /etc/systemd/system/danper-portal.service <<EOF
[Unit]
Description=Danper - Portal web (carga de datos y estado del pipeline)
After=network-online.target
Wants=network-online.target

[Service]
User=$USUARIO
EnvironmentFile=$ENTORNO
Environment=AWS_DEFAULT_REGION=$REGION
WorkingDirectory=$REPO/web
ExecStart=$VENV/bin/gunicorn --workers 1 --threads 4 --bind 127.0.0.1:8000 --timeout 120 portal:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable danper-portal
systemctl restart danper-portal
# El pipeline también debe ver DANPER_ESTADO para publicar su avance
systemctl is-active --quiet danper-ingesta && systemctl restart danper-ingesta

paso "5/5 Grafana público de solo lectura"
if [[ -n $DOMINIO ]]; then
    echo "DOMINIO_PUBLICO=$DOMINIO" > "$CONF"
elif [[ ! -f $CONF ]]; then
    echo "DOMINIO_PUBLICO=" > "$CONF"
fi
bash "$REPO/infra/aws/iniciar_grafana.sh"

sleep 2
paso "Comprobación"
printf 'Portal (local):            %s\n' "$(curl -s -m 5 http://127.0.0.1/salud-local || echo FALLA)"
printf 'Sin encabezado (esperado 403): %s\n' "$(curl -s -o /dev/null -w '%{http_code}' -m 5 http://127.0.0.1/estado)"
printf 'Con encabezado (esperado 200): %s\n' \
    "$(curl -s -o /dev/null -w '%{http_code}' -m 5 -H "X-Danper-Origen: $VALOR" http://127.0.0.1/estado)"
. "$CONF"
echo
echo "Para la distribución de CloudFront (origen > encabezado personalizado):"
echo "  Nombre: X-Danper-Origen"
echo "  Valor:  (ejecutar 'sudo cat $SECRETO'; no se muestra aquí)"
if [[ -n ${DOMINIO_PUBLICO:-} ]]; then
    echo
    echo "Listo: https://$DOMINIO_PUBLICO/  ·  /carga  ·  /estado"
else
    echo
    echo "Cuando exista la distribución, volver a ejecutar con --dominio dxxxx.cloudfront.net"
fi
