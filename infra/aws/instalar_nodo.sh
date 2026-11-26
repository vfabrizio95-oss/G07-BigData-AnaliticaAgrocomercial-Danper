#!/usr/bin/env bash
# Instala un nodo del cluster Danper en AWS (Ubuntu 24.04 en EC2).
#
# Uso (como root, desde el repositorio clonado en la máquina):
#   sudo bash infra/aws/instalar_nodo.sh master MASTER_HOST WORKER_1 WORKER_2 WORKER_3
#   sudo bash infra/aws/instalar_nodo.sh worker MASTER_HOST
#
#   MASTER_HOST  nombre DNS privado del master (ip-10-0-x-x.ec2.internal)
#   WORKER_N     nombres DNS privados de los workers (solo en el master)
#
# Qué hace:
#   1. Instala Java 11, Python 3.11, poppler-utils (pdftotext) y utilidades.
#   2. Crea el usuario de sistema "danper", que ejecuta Hadoop, Spark y el pipeline.
#   3. Descarga Hadoop 3.3.6 y Spark 3.5.1 de archive.apache.org y verifica su SHA-512.
#   4. Copia infra/aws/conf/ y reemplaza MASTER_HOST y WORKER_N_HOST.
#   5. Crea el entorno virtual /opt/danper/.venv con requirements.txt.
#   6. Crea servicios de systemd que arrancan solos al encender la máquina:
#        master: danper-namenode, danper-resourcemanager, danper-historyserver
#        worker: danper-datanode, danper-nodemanager
#   7. En el master: formatea HDFS (solo la primera vez) y crea las carpetas /danper.
#
# Se puede volver a ejecutar: no descarga de nuevo lo que ya existe y no vuelve
# a formatear HDFS. No abre puertos ni guarda contraseñas.
set -euo pipefail

HADOOP_VERSION=3.3.6
SPARK_VERSION=3.5.1
PG_JAR_VERSION=42.7.4
# Las versiones antiguas solo están en el archivo histórico de Apache.
# DANPER_APACHE_MIRROR permite usar otra copia con la misma estructura de carpetas.
APACHE=${DANPER_APACHE_MIRROR:-https://archive.apache.org/dist}

USUARIO=danper
BASE=/opt/danper
DATOS=/data/hadoop
DESCARGAS=${DANPER_DESCARGAS:-$BASE/descargas}
ENTORNO=/etc/danper/entorno

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
CONF="$REPO/infra/aws/conf"

uso() {
    sed -n '4,9p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
}

paso() { printf '\n==> %s\n' "$*"; }
error() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- argumentos
[[ $# -ge 2 ]] || uso
ROL=$1
MASTER_HOST=$2
shift 2
WORKERS=("$@")

[[ $ROL == master || $ROL == worker ]] || error "el rol debe ser master o worker, no '$ROL'"
[[ $EUID -eq 0 ]] || error "ejecutar con sudo"
[[ -f $CONF/core-site.xml ]] || error "no se encuentra $CONF (¿se clonó el repositorio completo?)"
if [[ $ROL == master && ${#WORKERS[@]} -eq 0 ]]; then
    error "en el master hay que indicar los nombres de los workers"
fi
if [[ $ROL == worker && ${#WORKERS[@]} -gt 0 ]]; then
    error "en un worker solo se indica el master"
fi

# ---------------------------------------------------------------- 1. paquetes
paso "1/7 Paquetes del sistema"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q software-properties-common curl ca-certificates git sudo \
    openjdk-11-jdk-headless poppler-utils
if ! command -v python3.11 >/dev/null; then
    # Ubuntu 24.04 trae Python 3.12; el proyecto usa 3.11 (igual que en local)
    add-apt-repository -y ppa:deadsnakes/ppa
    apt-get update -q
fi
apt-get install -y -q python3.11 python3.11-venv
JAVA_HOME=$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")

# ---------------------------------------------------------------- 2. usuario
paso "2/7 Usuario $USUARIO y carpetas"
id "$USUARIO" >/dev/null 2>&1 || useradd --create-home --shell /bin/bash "$USUARIO"
install -d -o "$USUARIO" -g "$USUARIO" "$BASE" "$BASE/jars" "$BASE/datasets" \
    "$DESCARGAS" "$DATOS" "$DATOS/tmp"
if [[ $ROL == master ]]; then
    install -d -o "$USUARIO" -g "$USUARIO" -m 700 "$DATOS/namenode"
else
    install -d -o "$USUARIO" -g "$USUARIO" -m 700 "$DATOS/datanode"
fi

# ---------------------------------------------------------------- 3. Hadoop y Spark
descargar() {  # descargar URL -> deja el archivo en $DESCARGAS y verifica su SHA-512
    local url=$1 archivo
    archivo="$DESCARGAS/$(basename "$url")"
    if [[ ! -f $archivo ]]; then
        echo "Descargando $(basename "$url") ..."
        curl -fSL --retry 3 -o "$archivo.parcial" "$url"
        mv "$archivo.parcial" "$archivo"
    fi
    local esperado obtenido
    # Los .sha512 de Apache vienen en varios formatos (el de Hadoop 3.3.6 incluso
    # nombra el archivo como -RC1): se toma solo la cadena de 128 dígitos hex
    esperado=$(curl -fsSL --retry 3 "$url.sha512" | tr -d ' \n\r\t' \
               | grep -oE '[0-9a-fA-F]{128}' | head -1 | tr 'A-F' 'a-f')
    [[ -n $esperado ]] || error "no se pudo leer $url.sha512"
    obtenido=$(sha512sum "$archivo" | cut -d' ' -f1)
    if [[ $esperado != "$obtenido" ]]; then
        rm -f "$archivo"
        error "SHA-512 no coincide para $(basename "$url"); se borró, volver a ejecutar"
    fi
    echo "SHA-512 verificado: $(basename "$url")"
}

instalar_tar() {  # instalar_tar ARCHIVO CARPETA_DESTINO ENLACE
    local archivo=$1 destino=$2 enlace=$3
    if [[ ! -d $destino ]]; then
        tar -xzf "$archivo" -C /opt
    fi
    chown -R "$USUARIO:$USUARIO" "$destino"
    ln -sfn "$destino" "$enlace"
}

paso "3/7 Hadoop $HADOOP_VERSION y Spark $SPARK_VERSION"
descargar "$APACHE/hadoop/common/hadoop-$HADOOP_VERSION/hadoop-$HADOOP_VERSION.tar.gz"
descargar "$APACHE/spark/spark-$SPARK_VERSION/spark-$SPARK_VERSION-bin-hadoop3.tgz"
instalar_tar "$DESCARGAS/hadoop-$HADOOP_VERSION.tar.gz" "/opt/hadoop-$HADOOP_VERSION" /opt/hadoop
instalar_tar "$DESCARGAS/spark-$SPARK_VERSION-bin-hadoop3.tgz" \
    "/opt/spark-$SPARK_VERSION-bin-hadoop3" /opt/spark

if [[ $ROL == master ]]; then
    # Driver JDBC de PostgreSQL: solo lo usa publicar_postgres.py, que corre en el master
    JAR="$BASE/jars/postgresql-$PG_JAR_VERSION.jar"
    if [[ ! -f $JAR ]]; then
        curl -fSL --retry 3 -o "$JAR" \
            "https://repo1.maven.org/maven2/org/postgresql/postgresql/$PG_JAR_VERSION/postgresql-$PG_JAR_VERSION.jar"
        chown "$USUARIO:$USUARIO" "$JAR"
    fi
fi

# ---------------------------------------------------------------- 4. configuración
paso "4/7 Configuración (infra/aws/conf)"
HCONF=/opt/hadoop/etc/hadoop
for f in core-site.xml hdfs-site.xml yarn-site.xml mapred-site.xml; do
    sed "s/MASTER_HOST/$MASTER_HOST/g" "$CONF/$f" > "$HCONF/$f"
done
sed "s/MASTER_HOST/$MASTER_HOST/g" "$CONF/spark-defaults.conf" > /opt/spark/conf/spark-defaults.conf
if [[ $ROL == master ]]; then
    printf '%s\n' "${WORKERS[@]}" > "$HCONF/workers"
fi
if ! grep -q "^export JAVA_HOME=$JAVA_HOME" "$HCONF/hadoop-env.sh"; then
    echo "export JAVA_HOME=$JAVA_HOME" >> "$HCONF/hadoop-env.sh"
fi
chown -R "$USUARIO:$USUARIO" "$HCONF" /opt/spark/conf

# Variables para los servicios (systemd) y para las sesiones (profile.d)
install -d /etc/danper
cat > "$ENTORNO" <<EOF
JAVA_HOME=$JAVA_HOME
HADOOP_HOME=/opt/hadoop
HADOOP_CONF_DIR=/opt/hadoop/etc/hadoop
YARN_CONF_DIR=/opt/hadoop/etc/hadoop
HADOOP_HEAPSIZE_MAX=1g
SPARK_HOME=/opt/spark
SPARK_CONF_DIR=/opt/spark/conf
PYSPARK_PYTHON=$BASE/.venv/bin/python
DANPER_HDFS_URI=hdfs://$MASTER_HOST:9000
DANPER_SPARK_MASTER=yarn
DANPER_DATASETS=$BASE/datasets
DANPER_PG_JAR=$BASE/jars/postgresql-$PG_JAR_VERSION.jar
EOF
cat > /etc/profile.d/danper.sh <<EOF
# Variables del cluster Danper (generado por infra/aws/instalar_nodo.sh)
set -a
. $ENTORNO
set +a
export PATH=\$PATH:/opt/hadoop/bin:/opt/hadoop/sbin:/opt/spark/bin:$BASE/.venv/bin
EOF

# ---------------------------------------------------------------- 5. Python
paso "5/7 Entorno virtual de Python"
if [[ ! -x $BASE/.venv/bin/python ]]; then
    sudo -u "$USUARIO" python3.11 -m venv "$BASE/.venv"
fi
sudo -u "$USUARIO" "$BASE/.venv/bin/pip" install -q --upgrade pip
sudo -u "$USUARIO" "$BASE/.venv/bin/pip" install -q -r "$REPO/requirements.txt"

# ---------------------------------------------------------------- 6. servicios
servicio() {  # servicio NOMBRE DESCRIPCION COMANDO
    cat > "/etc/systemd/system/$1.service" <<EOF
[Unit]
Description=Danper - $2
After=network-online.target
Wants=network-online.target

[Service]
User=$USUARIO
EnvironmentFile=$ENTORNO
ExecStart=$3
Restart=on-failure
RestartSec=10
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF
}

paso "6/7 Servicios de systemd"
if [[ $ROL == master ]]; then
    SERVICIOS=(danper-namenode danper-resourcemanager danper-historyserver)
    servicio danper-namenode "HDFS NameNode" "/opt/hadoop/bin/hdfs namenode"
    servicio danper-resourcemanager "YARN ResourceManager" "/opt/hadoop/bin/yarn resourcemanager"
    servicio danper-historyserver "Spark History Server" \
        "/opt/spark/bin/spark-class org.apache.spark.deploy.history.HistoryServer"
else
    SERVICIOS=(danper-datanode danper-nodemanager)
    servicio danper-datanode "HDFS DataNode" "/opt/hadoop/bin/hdfs datanode"
    servicio danper-nodemanager "YARN NodeManager" "/opt/hadoop/bin/yarn nodemanager"
fi
systemctl daemon-reload
systemctl enable "${SERVICIOS[@]}"

# ---------------------------------------------------------------- 7. arranque
como_danper() { sudo -u "$USUARIO" env $(grep -v '^#' "$ENTORNO" | xargs) "$@"; }

paso "7/7 Arranque"
if [[ $ROL == master ]]; then
    if [[ ! -d $DATOS/namenode/current ]]; then
        echo "Formateando HDFS (primera instalación)"
        como_danper /opt/hadoop/bin/hdfs namenode -format -nonInteractive -clusterId danper
    fi
    systemctl restart danper-namenode
    echo "Esperando al NameNode ..."
    for _ in $(seq 1 60); do
        como_danper /opt/hadoop/bin/hdfs dfsadmin -safemode get >/dev/null 2>&1 && break
        sleep 2
    done
    como_danper /opt/hadoop/bin/hdfs dfsadmin -safemode wait
    # Capas del data lake: ingesta_bronze.py lista /danper/bronze antes de subir nada
    como_danper /opt/hadoop/bin/hdfs dfs -mkdir -p /danper/spark-events /danper/yarn-logs \
        /danper/bronze /danper/silver /danper/gold /danper/calidad /danper/control \
        /tmp "/user/$USUARIO"
    como_danper /opt/hadoop/bin/hdfs dfs -chmod 1777 /tmp /danper/yarn-logs
    systemctl restart danper-resourcemanager danper-historyserver
else
    systemctl restart "${SERVICIOS[@]}"
fi

sleep 5
paso "Listo: nodo $ROL ($(hostname -f))"
for s in "${SERVICIOS[@]}"; do
    printf '  %-24s %s\n' "$s" "$(systemctl is-active "$s" || true)"
done
if [[ $ROL == master ]]; then
    echo
    echo "Cuando los workers estén instalados, revisar el cluster con:"
    echo "  sudo -u $USUARIO bash $REPO/infra/aws/estado_cluster.sh"
fi
