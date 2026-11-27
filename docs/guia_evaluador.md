# Guía del evaluador: plataforma Danper G07 en vivo

Esta guía permite comprobar, sin instalar nada y sin acceso a la cuenta de AWS,
que la plataforma funciona de punta a punta: un dato nuevo entra por la página
de carga, recorre todo el pipeline (Bronze → Silver → Gold → modelo ya entrenado
→ PostgreSQL) y aparece en el tablero. Sirve tanto para una persona como para un
asistente automático (IA) que siga los pasos.

> La URL y la contraseña se entregan en el informe (Anexo: guía del evaluador),
> no en este repositorio público. Abajo aparecen como `<URL>` y `<CONTRASEÑA>`.

## 1. Enlaces

| Qué | Dirección | Acceso |
|---|---|---|
| Tablero (Grafana) | `<URL>/` | Libre, solo lectura |
| Carga de datos nuevos | `<URL>/carga` | Usuario `evaluador` y `<CONTRASEÑA>` |
| Estado del pipeline | `<URL>/estado` | Libre; se actualiza sola cada 10 s |
| Estado en JSON | `<URL>/api/estado` | Libre |

## 2. Prueba recomendada (unos 6 minutos)

1. Abrir `<URL>/estado` y anotar:
   - **Último dato de ingreso a planta** (por ejemplo, `ALCACHOFA 2024-12`).
   - Los meses del **pronóstico vigente** (por ejemplo, `2025-01` a `2025-03`).
   - La **fecha de entrenamiento del modelo** (`modelo_entrenado_hasta`).
2. Abrir `<URL>/carga`, ingresar con el usuario `evaluador` y la contraseña.
3. Pulsar **«Inyectar dato de prueba»**. La página genera y carga dos meses
   **simulados** de ingreso de materia prima a planta (alcachofa y espárrago),
   con el formato de la fuente oficial y marcados como `DEMO`, y lleva a la
   página de estado.
4. En `<URL>/estado`, la **fase** pasa por:
   - «esperando la sincronización con S3 (hasta 60 s)»,
   - «procesando», con cada etapa (Bronze, Silver agroindustria, Gold,
     Modelo (aplicar) y PostgreSQL) y sus segundos,
   - «terminado», unos 5 minutos después.
5. Comprobar el resultado:
   - En `/estado` (o `/api/estado`): el **último dato de ingreso a planta**
     avanzó dos meses, el **pronóstico vigente** se desplazó dos meses y la
     **fecha de entrenamiento del modelo no cambió** (el modelo se aplica, no se
     reentrena).
   - En el tablero (`<URL>/`), sin recargar la página: «Último dato de ingreso a
     planta», el panel «Pronóstico vigente» y las líneas de ingreso real del
     panel del plan anual.

La prueba se puede repetir: cada vez se cargan los dos meses siguientes.

## 3. Prueba con un archivo propio (opcional)

En `<URL>/carga`, sección «Subir un archivo»:

| Fuente | Formato aceptado |
|---|---|
| Ingreso a planta agroindustrial | Excel `.xlsx` con el formato de la Gerencia Regional de Agricultura de La Libertad: cuadro N.º 7 (alcachofa) o 64 (espárrago), fila «AÑO TOTAL ENE … DIC». El nombre debe contener `ALCACHOFA` o `ESPARRAGO`. En la misma página hay ejemplos descargables. |
| Reporte diario del Gran Mercado Mayorista de Lima | PDF de MIDAGRI con su nombre original, terminado en `-DD-MM-AAAA.pdf`. Cambia los paneles del GMML y «Último reporte GMML». |

Un archivo con otro formato se rechaza con un mensaje que explica el motivo; no
llega al pipeline. Un archivo idéntico a uno ya cargado no se procesa de nuevo
(se reconoce por su huella SHA-256).

## 4. Respuesta de `/api/estado`

Campos principales:

| Campo | Significado |
|---|---|
| `fase` | `terminado`, `procesando`, `error` o «esperando la sincronización con S3» |
| `servicio_ingesta_activo` | `true` si el servicio que vigila S3 revisó en los últimos minutos |
| `ultima_carga` | Archivos recibidos por el portal, con hora y detalle |
| `pipeline.etapas` | Cada etapa de la última corrida con su estado y segundos |
| `modelo.ultimo_registro` | Último mes de ingreso a planta por cultivo |
| `modelo.pronostico_vigente` | Pronóstico de los 3 meses siguientes: `prom_3a_t` (método recomendado) y `lineal_t` (Spark MLlib) |
| `modelo.modelo_entrenado_hasta` | Último mes con el que se entrenó el modelo; no cambia al llegar datos |

## 5. Qué se está demostrando

- **Ingesta automática:** el archivo se sube al bucket S3 y el servicio
  `danper-ingesta` del master lo detecta en menos de un minuto.
- **Data lake por capas en HDFS** sobre un cluster de 1 master y 3 workers en
  Amazon EC2, con Spark sobre YARN.
- **Modelo ya entrenado:** el `PipelineModel` de Spark MLlib se cargó desde HDFS
  y se aplicó con `transform()` a los datos nuevos, sin reentrenar.
- **Capa de consumo:** Gold se publica en Amazon RDS (PostgreSQL) y el tablero
  de Grafana lo muestra con un usuario de solo lectura.

Los datos de prueba son simulados (la fuente oficial aún no publica 2025) y se
retiran después de la evaluación con `infra/aws/retirar_demo.sh`.
