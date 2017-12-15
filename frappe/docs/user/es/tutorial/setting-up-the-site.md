# Configurando el Site

Vamos a crear un nuevo Site llamado `library`.

*Nota: Antes de crear cualquier Site, necesitas hacer unos cambios en su instalación de MariaDB.*
*Copia la siguiente configuración por defecto de ERPNext en su archivo `my.cnf`.*

    [mysqld]
    innodb-file-format=barracuda
    innodb-file-per-table=1
    innodb-large-prefix=1
    character-set-client-handshake = FALSE
    character-set-server = utf8mb4
    collation-server = utf8mb4_unicode_ci

    [mysql]
    default-character-set = utf8mb4

Ahora puedes instalar un nuevo site, ejecutando el comando `bench new-site library`.

La ejecución del comando anterior va a generar una nueva base de datos, un directorio en la carpeta sites y va a instalar `frappe` (el cual también es una aplicación!) en el nuevo site.
 La aplicación `frappe` tiene dos módulos integrados que son **Core** y **Website**. El módulo Core contiene los modelos básicos para la aplicación. Frappé es un Framework con muchas funcionalidades incluidas y viene con muchos modelos integrados. Estos modelos son llamados **DocTypes**. Vamos a ver más de esto en lo adelante.

	$ bench new-site library
	MySQL root password:
	Installing frappe...
	Updating frappe                     : [========================================]
	Updating country info               : [========================================]
	Set Administrator password:
	Re-enter Administrator password:
	Installing fixtures...
	*** Scheduler is disabled ***

### Estructura de un Site

Un nuevo directorio ha sido creado dentro de la carpeta `sites` llamado `library`. La estructura siguiente es la que trae por defecto un site.

	.
	├── locks
	├── private
	│   └── backups
	├── public
	│   └── files
	└── site_config.json

1. `public/files` es donde se almacenan los archivos subidos por los usuarios.
1. `private/backups` es donde se almacenan los backups o copias de respaldo.
1. `site_config.json` es donde todas las configuraciones a nivel de sites son almacenadas.

### Configurando un Site por defecto

En caso que tengas varios sites en tu Bench, debes usar `bench use [nombre_site]` para especificar el site por defecto.

Ejemplo:

	$ bench use library

### Instalar Aplicaciones

Ahora vamos a instalar nuestra aplicación `library_management` en nuestro site `library`.

1. Instalar la aplicación library_management en el site library se logra ejecutando el siguiente comando: `bench --site [nombre_site] install-app [nombre_app]`

Ejemplo:

	$ bench --site library install-app library_management

{next}
