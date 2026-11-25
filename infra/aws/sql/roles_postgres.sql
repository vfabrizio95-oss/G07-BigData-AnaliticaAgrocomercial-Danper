-- Roles de PostgreSQL con mínimo privilegio para Danper (RDS for PostgreSQL 16).
--
-- Se ejecuta UNA vez, desde el master, con el usuario administrador de RDS,
-- conectado a la base danper. Las contraseñas se pasan como variables de psql
-- (vienen de Parameter Store; no se escriben en este archivo):
--
--   psql "host=<endpoint-rds> dbname=danper user=<admin> sslmode=require" \
--        -v clave_etl="$CLAVE_ETL" -v clave_grafana="$CLAVE_GRAFANA" \
--        -f infra/aws/sql/roles_postgres.sql
--
-- Resultado:
--   etl_escritor    publica Gold (scripts/publicar_postgres.py). Es dueño de los
--                   esquemas gold y gold_staging; no puede crear bases, roles
--                   ni objetos en public.
--   grafana_lector  solo SELECT sobre el esquema gold (tablero de Grafana).
--   PUBLIC          sin acceso a la base danper.
--
-- Se puede volver a ejecutar: no falla si los roles o esquemas ya existen y
-- vuelve a fijar las contraseñas.

\set ON_ERROR_STOP on

-- 1. Roles (sin superusuario, sin crear bases ni roles) ----------------------
SELECT 'CREATE ROLE etl_escritor LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'etl_escritor') \gexec
SELECT 'CREATE ROLE grafana_lector LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'grafana_lector') \gexec

ALTER ROLE etl_escritor PASSWORD :'clave_etl';
ALTER ROLE grafana_lector PASSWORD :'clave_grafana';

-- Un lector nunca escribe, aunque alguien le otorgue permisos por error
ALTER ROLE grafana_lector SET default_transaction_read_only = on;

-- En RDS el administrador no es superusuario: para crear un esquema a nombre
-- de etl_escritor necesita ser miembro de ese rol (PostgreSQL 16).
GRANT etl_escritor TO CURRENT_USER;

-- 2. Base de datos: nadie entra salvo los roles de Danper ---------------------
REVOKE ALL ON DATABASE danper FROM PUBLIC;
GRANT CONNECT ON DATABASE danper TO etl_escritor, grafana_lector;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- 3. Esquemas: etl_escritor es su dueño --------------------------------------
-- publicar_postgres.py escribe en gold_staging y, en una sola transacción,
-- mueve cada tabla a gold (ALTER TABLE ... SET SCHEMA). Para eso necesita ser
-- dueño de las tablas y tener CREATE en ambos esquemas.
CREATE SCHEMA IF NOT EXISTS gold AUTHORIZATION etl_escritor;
CREATE SCHEMA IF NOT EXISTS gold_staging AUTHORIZATION etl_escritor;
ALTER SCHEMA gold OWNER TO etl_escritor;
ALTER SCHEMA gold_staging OWNER TO etl_escritor;

-- 4. Lectura para Grafana: solo gold, nunca gold_staging ----------------------
-- publicar_postgres.py detecta a grafana_lector por este USAGE y le vuelve a
-- dar SELECT sobre cada tabla que publica.
GRANT USAGE ON SCHEMA gold TO grafana_lector;
GRANT SELECT ON ALL TABLES IN SCHEMA gold TO grafana_lector;
ALTER DEFAULT PRIVILEGES FOR ROLE etl_escritor IN SCHEMA gold
    GRANT SELECT ON TABLES TO grafana_lector;
REVOKE ALL ON SCHEMA gold_staging FROM grafana_lector;

-- 5. Evidencia para el informe ------------------------------------------------
\echo
\echo '== Roles de Danper =='
SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolcanlogin
FROM pg_roles WHERE rolname IN ('etl_escritor', 'grafana_lector') ORDER BY 1;
\echo '== Esquemas y permisos =='
\dn+ gold*
