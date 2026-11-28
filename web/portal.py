"""Portal web de la plataforma Danper: carga de datos nuevos y estado del pipeline.

Corre en el master detrás de nginx (infra/aws/conf/nginx-danper.conf), que
publica en la misma URL:
    /            tablero de Grafana (solo lectura, sin iniciar sesión)
    /carga       subir un archivo nuevo o inyectar un dato de prueba (con contraseña)
    /estado      avance del pipeline con el último archivo recibido
    /api/estado  lo mismo en JSON, para un evaluador automático

Los archivos se suben al bucket S3 (s3://<bucket>/datasets/<fuente>/). Desde
ahí el servicio danper-ingesta los copia al master y run_pipeline.py los lleva
por Bronze, Silver, Gold, el modelo (aplicar) y PostgreSQL.

Configuración (variables de entorno):
    DANPER_PORTAL_MODO   "aws" (por defecto) o "local": en local los archivos se
                         copian a DANPER_DATASETS en vez de subirse a S3
    DANPER_PORTAL_CLAVE  contraseña de /carga; en AWS se lee de Parameter Store
                         (/danper/portal/clave) si no se define
    DANPER_BUCKET        bucket; en AWS se lee de /danper/s3/bucket si no se define
    AWS_DEFAULT_REGION   región de AWS (el instalador la fija)

Uso local de prueba:
    DANPER_PORTAL_MODO=local DANPER_PORTAL_CLAVE=prueba \\
        .venv/bin/flask --app web/portal.py run --port 8000
En el master lo ejecuta el servicio danper-portal (infra/aws/instalar_portal.sh).
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import hmac
import os
import re
import shutil
import sys
import time

from flask import (Flask, flash, jsonify, redirect, render_template, request,
                   send_file, session, url_for)

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import config  # noqa: E402
import estado  # noqa: E402
from extractor_agroindustria import extraer_agroindustria  # noqa: E402
from generar_demo_agroindustria import generar  # noqa: E402

MODO = os.environ.get("DANPER_PORTAL_MODO", "aws")
USUARIO = "admin"
MAX_MB = 20
GMML = re.compile(r"mercado-mayorista-de-lima-(\d{2})-(\d{2})-(\d{4})\.pdf$", re.IGNORECASE)

app = Flask(__name__)
app.secret_key = os.urandom(32)  # un solo proceso (gunicorn -w 1): las sesiones no se pierden
app.config["MAX_CONTENT_LENGTH"] = (MAX_MB + 1) * 1024 * 1024


# ------------------------------------------------------------------ AWS
_aws = {}


def parametro(nombre):
    import boto3
    ssm = _aws.setdefault("ssm", boto3.client("ssm"))
    return ssm.get_parameter(Name=nombre, WithDecryption=True)["Parameter"]["Value"]


def bucket():
    if "bucket" not in _aws:
        _aws["bucket"] = os.environ.get("DANPER_BUCKET") or parametro("/danper/s3/bucket")
    return _aws["bucket"]


def clave_portal():
    if "clave" not in _aws:
        _aws["clave"] = os.environ.get("DANPER_PORTAL_CLAVE") or parametro("/danper/portal/clave")
    return _aws["clave"]


def s3():
    import boto3
    return _aws.setdefault("s3", boto3.client("s3"))


def guardar(origen, relativo):
    """Deja el archivo en datasets/<relativo>: S3 en AWS, la carpeta local en modo local."""
    if MODO == "local":
        destino = config.DATASETS / relativo
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origen, destino)
        return str(destino)
    s3().upload_file(str(origen), bucket(), f"datasets/{relativo}")
    return f"s3://{bucket()}/datasets/{relativo}"


def nombres_demo():
    """Nombres de los Excel DEMO ya cargados (para elegir los meses siguientes)."""
    if MODO == "local":
        carpeta = config.DATASETS / "agroindustria"
        return [p.name for p in carpeta.glob("*DEMO*")] if carpeta.is_dir() else []
    pagina = s3().list_objects_v2(Bucket=bucket(), Prefix="datasets/agroindustria/")
    return [o["Key"].rsplit("/", 1)[-1] for o in pagina.get("Contents", []) if "DEMO" in o["Key"]]


# ------------------------------------------------------------------ registro de cargas
def registrar_carga(archivos, origen):
    cargas = estado.leer("cargas") or []
    cargas.insert(0, {"recibido": estado.ahora(), "origen": origen, "archivos": archivos})
    estado.escribir("cargas", cargas[:20])


def resumen_estado():
    """Todo lo que muestra /estado, en un diccionario (también es /api/estado)."""
    pipeline = estado.leer("pipeline") or {}
    modelo = estado.leer("modelo") or {}
    cargas = estado.leer("cargas") or []
    ahora = datetime.now(timezone.utc)

    def fecha(texto):
        try:
            return datetime.fromisoformat(texto)
        except (TypeError, ValueError):
            return None

    revision = fecha(pipeline.get("ultima_revision"))
    intervalo = pipeline.get("vigilando_cada_s") or 60
    servicio_activo = bool(revision and ahora - revision < timedelta(seconds=3 * intervalo + 120))

    ultima_carga = cargas[0] if cargas else None
    fase = pipeline.get("estado", "sin corridas")
    if ultima_carga and fase != "procesando":
        inicio = fecha(pipeline.get("inicio"))
        recibido = fecha(ultima_carga["recibido"])
        if recibido and (inicio is None or recibido > inicio):
            fase = "esperando la sincronización con S3 (hasta 2 min)"

    return {
        "consultado": ahora.isoformat(timespec="seconds"),
        "servicio_ingesta_activo": servicio_activo,
        "fase": fase,
        "ultima_carga": ultima_carga,
        "pipeline": pipeline,
        "modelo": modelo,
        "tablero": "/",
        "ayuda": ("Tras subir un archivo, la fase pasa a 'procesando' en menos de 2 minutos y a "
                  "'terminado' unos 4 minutos después; entonces el tablero (/) ya muestra el dato nuevo."),
    }


# ------------------------------------------------------------------ validación
def validar(fuente, ruta, nombre):
    """Devuelve (ruta relativa en datasets/, detalle) o lanza ValueError con un mensaje claro."""
    if ruta.stat().st_size > MAX_MB * 1024 * 1024:
        raise ValueError(f"El archivo supera {MAX_MB} MB.")
    cabecera = ruta.read_bytes()[:4]
    if fuente == "abastecimiento":
        m = GMML.search(nombre)
        if not nombre.lower().endswith(".pdf") or cabecera != b"%PDF":
            raise ValueError("Para el GMML se espera un PDF.")
        if not m:
            raise ValueError("El nombre del PDF debe terminar como el de MIDAGRI: "
                             "'...-mercado-mayorista-de-lima-DD-MM-AAAA.pdf'.")
        return f"abastecimiento/gmml_{m.group(3)}/{nombre}", "Reporte diario del GMML"
    if fuente == "agroindustria":
        if not nombre.lower().endswith(".xlsx") or cabecera != b"PK\x03\x04":
            raise ValueError("Para el ingreso a planta se espera un Excel .xlsx.")
        if not re.search(r"ALCACHOFA|ESPARRAGO", nombre, re.IGNORECASE):
            raise ValueError("El nombre del Excel debe contener ALCACHOFA o ESPARRAGO.")
        with TemporaryDirectory() as carpeta:
            copia = Path(carpeta) / nombre
            shutil.copyfile(ruta, copia)
            try:
                datos, _, _ = extraer_agroindustria(carpeta)
            except Exception as error:  # formato distinto al de la fuente oficial
                raise ValueError(f"El Excel no tiene el formato de la fuente: {error}") from error
        if datos.empty:
            raise ValueError("El Excel no tiene filas de ingreso a planta (cuadro 7 o 64) "
                             "con el formato de la fuente.")
        meses = sorted({f"{a}-{m:02d}" for a, m in zip(datos["anio"], datos["numero_mes"])})
        return f"agroindustria/{nombre}", f"Ingreso a planta: {len(datos)} valores ({', '.join(meses[-4:])})"
    raise ValueError("Fuente no admitida.")


def limpiar_nombre(nombre):
    nombre = Path(nombre or "").name
    nombre = re.sub(r"[^A-Za-z0-9 ._-]", "", nombre).strip()
    if not nombre:
        raise ValueError("Nombre de archivo vacío o no válido.")
    return nombre


# ------------------------------------------------------------------ páginas
def requiere_sesion():
    return session.get("usuario") == USUARIO


@app.get("/salud")
def salud():
    return "ok"


@app.get("/carga")
def carga():
    if not requiere_sesion():
        return render_template("ingresar.html")
    return render_template("carga.html", max_mb=MAX_MB, demos=sorted(nombres_demo()))


@app.post("/carga/ingresar")
def ingresar():
    usuario = request.form.get("usuario", "")
    clave = request.form.get("clave", "")
    if usuario == USUARIO and hmac.compare_digest(clave.encode(), clave_portal().encode()):
        session["usuario"] = USUARIO
        return redirect(url_for("carga"))
    time.sleep(1)  # frena los intentos repetidos
    flash("Usuario o contraseña incorrectos.", "error")
    return redirect(url_for("carga"))


@app.post("/carga/salir")
def salir():
    session.clear()
    return redirect(url_for("carga"))


@app.post("/carga/archivo")
def subir_archivo():
    if not requiere_sesion():
        return redirect(url_for("carga"))
    fuente = request.form.get("fuente", "")
    archivo = request.files.get("archivo")
    try:
        if archivo is None or not archivo.filename:
            raise ValueError("Elige un archivo.")
        nombre = limpiar_nombre(archivo.filename)
        with TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / nombre
            archivo.save(ruta)
            relativo, detalle = validar(fuente, ruta, nombre)
            destino = guardar(ruta, relativo)
    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("carga"))
    registrar_carga([{"archivo": relativo, "detalle": detalle, "destino": destino}], "archivo subido")
    flash(f"Archivo recibido: {relativo}. Sigue su avance en esta página.", "ok")
    return redirect(url_for("pagina_estado"))


@app.post("/carga/prueba")
def inyectar_prueba():
    if not requiere_sesion():
        return redirect(url_for("carga"))
    with TemporaryDirectory() as carpeta:
        lineas = generar(carpeta, factor=1.3, continuar=True, nombres_previos=nombres_demo())
        archivos = []
        for linea in lineas:
            ruta, _, detalle = linea.partition(": ")
            relativo = f"agroindustria/{Path(ruta).name}"
            archivos.append({"archivo": relativo, "detalle": f"Simulado (DEMO): {detalle}",
                             "destino": guardar(Path(ruta), relativo)})
    registrar_carga(archivos, "dato de prueba (simulado)")
    flash("Dato de prueba enviado: " + ", ".join(a["archivo"] for a in archivos), "ok")
    return redirect(url_for("pagina_estado"))


@app.get("/carga/ejemplo/<cultivo>")
def ejemplo(cultivo):
    """Excel de ejemplo con los meses siguientes, para subirlo con el formulario."""
    if not requiere_sesion():
        return redirect(url_for("carga"))
    cultivo = cultivo.upper()
    if cultivo not in ("ALCACHOFA", "ESPARRAGO"):
        return "Cultivo no válido", 404
    carpeta = TemporaryDirectory()
    linea = generar(carpeta.name, factor=1.3, cultivos=[cultivo], continuar=True,
                    nombres_previos=nombres_demo())[0]
    ruta = Path(linea.partition(": ")[0])
    respuesta = send_file(ruta, as_attachment=True, download_name=ruta.name)
    respuesta.call_on_close(carpeta.cleanup)
    return respuesta


@app.get("/estado")
def pagina_estado():
    return render_template("estado.html", e=resumen_estado())


@app.get("/api/estado")
def api_estado():
    return jsonify(resumen_estado())


@app.errorhandler(413)
def demasiado_grande(_):
    flash(f"El archivo supera {MAX_MB} MB.", "error")
    return redirect(url_for("carga"))
