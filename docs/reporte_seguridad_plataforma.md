# 3.8. Seguridad de la plataforma

## Configuración actual

El proyecto de analítica agrocomercial de Danper utiliza Apache
Hadoop HDFS y Apache Spark en una máquina virtual Debian 12,
bajo una arquitectura on-premise.

Se realizó un diagnóstico de seguridad mediante comandos de
consulta, sin modificar la configuración del sistema.

### Control de acceso e integridad

Las capas Silver y Gold de HDFS presentan permisos `drwxr-xr-x`
(755), con el usuario `danna` como propietario y el grupo
`supergroup`.

La propiedad `dfs.permissions.enabled=true` confirma que la
comprobación de permisos de HDFS está habilitada.

Estos permisos permiten al propietario modificar los directorios,
mientras que otros usuarios pueden acceder y consultar su contenido.
Sin embargo, el acceso de lectura resulta amplio para un entorno
empresarial.

### Autenticación y credenciales

La configuración `hadoop.security.authentication=simple` indica
que Hadoop utiliza autenticación simple y no Kerberos.

La gestión segura de credenciales no fue verificada directamente.
Para producción se propone utilizar autenticación Kerberos,
cuentas de servicio independientes, privilegios mínimos y un
mecanismo seguro de almacenamiento y rotación de credenciales,
evitando contraseñas o claves dentro del código y del repositorio.

### Cifrado en reposo

La consulta `hdfs crypto -listZones` no devolvió zonas de cifrado.

Por tanto, no se evidenció el uso de zonas cifradas de HDFS.
Para producción se propone habilitar cifrado en reposo mediante
zonas de cifrado de HDFS y una gestión controlada de claves.

### Cifrado en tránsito

Se identificaron las siguientes configuraciones:

- `dfs.encrypt.data.transfer=false`
- `dfs.http.policy=HTTP_ONLY`
- `dfs.data.transfer.protection`: propiedad no definida.

La transferencia cifrada de datos HDFS no está habilitada y
la política de los servicios web consultados utiliza HTTP.
Para producción se propone configurar TLS/HTTPS y proteger
las comunicaciones de HDFS y sus servicios asociados.

## Conclusión

La plataforma dispone de controles básicos de permisos HDFS,
pero presenta limitaciones en autenticación y cifrado.

En el entorno académico actual se documentaron las
configuraciones existentes. Para un despliegue productivo
se recomienda implementar autenticación robusta, control
de acceso por roles, cifrado en reposo y tránsito, y gestión
segura de credenciales para preservar la integridad y
confidencialidad de los datos.
