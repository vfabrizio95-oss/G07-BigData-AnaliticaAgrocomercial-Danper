#!/usr/bin/env bash
# Crea y arranca el servicio danper-ingesta en el master (una sola vez).
#
# El servicio ejecuta infra/aws/ingesta_continua.sh: sincroniza S3 cada 60 s
# y corre el pipeline completo con cada archivo nuevo. Arranca solo al
# encender el master y se reinicia si falla.
#
# Requisitos: el cluster instalado (instalar_nodo.sh), RDS preparado
# (preparar_rds.sh) y el modelo entrenado una vez:
#   spark-submit scripts/modelo_abastecimiento.py
#
# Uso (en el master, con un usuario que tenga sudo):
#   sudo bash infra/aws/activar_ingesta.sh            # crear y arrancar
#   sudo bash infra/aws/activar_ingesta.sh --detener  # detener y desactivar
#
# Ver lo que hace (por ejemplo, en la demostración):
#   journalctl -u danper-ingesta -f
set -euo pipefail

[[ $EUID -eq 0 ]] || { echo "ERROR: ejecutar con sudo" >&2; exit 1; }
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
UNIDAD=/etc/systemd/system/danper-ingesta.service

if [[ ${1:-} == --detener ]]; then
    systemctl disable --now danper-ingesta 2>/dev/null || true
    echo "danper-ingesta detenido y desactivado"
    exit 0
fi

[[ -f /etc/danper/entorno ]] || { echo "ERROR: falta /etc/danper/entorno; ¿se ejecutó instalar_nodo.sh?" >&2; exit 1; }

cat > "$UNIDAD" <<EOF
[Unit]
Description=Danper - Ingesta automática (S3 -> pipeline -> PostgreSQL)
After=network-online.target danper-namenode.service danper-resourcemanager.service
Wants=network-online.target

[Service]
User=danper
EnvironmentFile=/etc/danper/entorno
WorkingDirectory=$REPO
ExecStart=/bin/bash $REPO/infra/aws/ingesta_continua.sh
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now danper-ingesta
sleep 3
systemctl --no-pager --lines=5 status danper-ingesta || true
echo
echo "Seguir el pipeline: journalctl -u danper-ingesta -f"
