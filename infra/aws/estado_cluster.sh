#!/usr/bin/env bash
# Revisa el estado del cluster Danper. Se ejecuta en el master como usuario danper:
#
#   sudo -u danper bash infra/aws/estado_cluster.sh           # estado
#   sudo -u danper bash infra/aws/estado_cluster.sh --prueba  # estado + trabajo de Spark en YARN
#
# Muestra (y sirve como evidencia para el informe):
#   - Servicios del master (systemd).
#   - HDFS: DataNodes vivos, capacidad y salud (fsck).
#   - YARN: NodeManagers activos con su memoria y núcleos.
#   - Con --prueba: ejecuta el ejemplo Pi de Spark en YARN y muestra en qué
#     workers corrieron los executors.
set -uo pipefail

ENTORNO=/etc/danper/entorno
[[ -f $ENTORNO ]] || { echo "ERROR: falta $ENTORNO; ¿se ejecutó instalar_nodo.sh?" >&2; exit 1; }
set -a; . "$ENTORNO"; set +a
export PATH=$PATH:/opt/hadoop/bin:/opt/spark/bin

titulo() { printf '\n===== %s =====\n' "$*"; }
ESPERADOS=$(grep -c . "$HADOOP_CONF_DIR/workers" 2>/dev/null || echo "?")

titulo "Servicios del master"
for s in danper-namenode danper-resourcemanager danper-historyserver; do
    printf '%-26s %s\n' "$s" "$(systemctl is-active "$s")"
done

titulo "HDFS"
hdfs dfsadmin -report 2>/dev/null \
    | grep -E '^(Configured Capacity|DFS Used:|DFS Remaining:|Live datanodes|Dead datanodes|Name:|Hostname:)'
VIVOS=$(hdfs dfsadmin -report -live 2>/dev/null | sed -n 's/^Live datanodes (\([0-9]*\)).*/\1/p')
echo "DataNodes vivos: ${VIVOS:-0} de $ESPERADOS"
echo
echo "Salud del sistema de archivos:"
hdfs fsck / 2>/dev/null | grep -E 'Status:|Under-replicated blocks|Missing blocks|Default replication'

titulo "YARN"
yarn node -list -showDetails 2>/dev/null \
    | grep -E 'Total Nodes|RUNNING|Configured Resources' | sed 's/^[[:space:]]*/  /'
echo "(Si muestra 0 nodos justo después de arrancar, esperar un minuto y repetir)"

if [[ ${1:-} == --prueba ]]; then
    titulo "Prueba: Spark Pi en YARN"
    SALIDA=$(mktemp)
    spark-submit --master yarn --conf spark.executor.instances="${ESPERADOS//\?/1}" \
        /opt/spark/examples/src/main/python/pi.py 20 >"$SALIDA" 2>&1
    CODIGO=$?
    grep -E '^Pi is roughly' "$SALIDA" || true
    APP=$(grep -oE 'application_[0-9]+_[0-9]+' "$SALIDA" | head -1)
    echo "Aplicación de YARN: ${APP:-no encontrada}"
    if [[ -n $APP ]]; then
        echo "Contenedores de YARN por worker (executors + 1 ApplicationMaster):"
        yarn logs -applicationId "$APP" -show_container_log_info 2>/dev/null \
            | grep -oE 'Container: container_[0-9_e]+ on [^ ]+' | awk '{print "  " $4}' | sort | uniq -c
    fi
    if [[ $CODIGO -ne 0 ]]; then
        echo "La prueba falló (código $CODIGO). Últimas líneas:"
        tail -20 "$SALIDA"
    fi
    rm -f "$SALIDA"
    exit $CODIGO
fi
