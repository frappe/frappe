# Bench Commands Cheatsheet

### Uso General
* `bench --version` - Muestra la versión del bench
* `bench src` - Muestra el directorio repo del bench
* `bench --help` - Muestra todos los comandos y ayudas
* `bench [command] --help` - Muestra la ayuda para un comando
* `bench init [bench-name]` - Crea un nuevo bench (Ejecutar desde Home)
* `bench --site [site-name] COMMAND` - Especificar un site para el comando
* `bench update` - Buscar los últimos cambios de bench-repo y todas las aplicaciones, aplica parches, crea los JS y CSS, y realiza la migración.
  * `--pull`                Hace un Pull a todas las aplicaciones en el bench
  * `--patch`               Ejecuta las migraciones para todos los sites en el bench
  * `--build`               Crea los JS y CSS para el bench
  * `--bench`               Actualiza el bench
  * `--requirements`        Actualiza los requerimientos
  * `--restart-supervisor`  Reinicia los procesos de supervisor despues de actualizar
  * `--upgrade` Realiza migraciones mayores (Eg. ERPNext 6 -> 7)
  * `--no-backup`			  No crea una copia de respaldo antes de actualizar
* `bench restart` Reinicia todos los servicios del bench
* `bench backup` Copia de respaldo
* `bench backup-all-sites` Copia de respaldo a todos los sites
  * `--with-files` Copia de respaldo a los sites con los archivos
* `bench restore` Restaurar
  * `--with-private-files` Restaura un site con todos los archivos privados (Ruta al archivo .tar)
  * `--with-public-files` Restaura un site con todos los archivos públicos (Ruta al archivo .tar)
* `bench migrate` Leerá los archivos JSON y realizará los cambios en la base de datos.

###Configuración
* `bench config` - Cambiar las configuraciones del bench
  * `auto_update [on/off]`          Activa/Desactiva las actualizaciones automáticas para el bench
  * `dns_multitenant [on/off]`      Activa/Desactiva DNS Multitenancy
  * `http_timeout`                  Establece un timeout para http
  * `restart_supervisor_on_update`  Activa/Desactiva el reinicio automático de supervisor
  * `serve_default_site`            Configurar nginx para que sirva el sitio predeterminado en...
  * `update_bench_on_update`        Activa/Desactiva las actualizaciones en un bench corriendo
* `bench setup` - Configurar componentes
  * `auto-update`  Añade un cronjob para actualizaciones automática del bench
  * `backups    `  Añade un cronjob para las copias de respaldo del bench
  * `config     `  sobreescribe o crea config.json
  * `env        `  Configurar un virtualenv para el bench
  * `nginx      `  generar configuraciones para nginx
  * `procfile   `  Configura el archivo Procfile para bench start
  * `production `  Configura el bench para producción
  * `redis      `  genera las configuraciones para redis cache
  * `socketio   `  Configura las dependencias de node para el servidor socketio
  * `sudoers    `  Agrega comandos a la sudoers para su ejecución
  * `supervisor `  Genera las configuraciones para supervisor
  * `add-domain `  agrega un dominio personalizado para un site
  * `firewall `    configura un firewall y bloquea todos los puertos en excepción el 22, 80 y 443
  * `ssh-port `    cambia el puerto por defecto para conexiones ssh


###Desarrollo
* `bench new-app [app-name]` Crea una nueva app
* `bench get-app [repo-link]` - Descarga una app desde un repositorio git y la instala
* `bench install-app [app-name]` Instala aplicaciones existentes
* `bench remove-from-installed-apps [app-name]` Remueve aplicaciones de la liste de aplicaciones
* `bench uninstall-app [app-name]` Elimina la aplicación y todo lo relaciones a esa aplicación (Bench necesita estar corriendo)
* `bench remove-app [app-name]` Eliminar una aplicación completamente del bench
* `bench --site [sitename] --force reinstall ` Reiniciar con una base de datos nueva (Atención: Va a borrar la base de datos anterior)
* `bench new-site [sitename]` - Crea un nuevo site
  * `--db-name`                Nombre de la base de datos
  * `--mariadb-root-username`  Nombre de usuario de Root
  * `--mariadb-root-password`  Contraseña del usuario Root
  * `--admin-password`         Contraseña del usuario Administrator para un nuevo site
  * `--verbose`                     Verbose
  * `--force`                       Forzar la restauración si el site/base de datos existen.
  * `--source_sql`             Inicializar una base de datos con un archivo SQL
  * `--install-app`            Instalar una aplicación despues de haber instalado el bench
* `bench use [site]` Configura el site por defecto
* `bench drop-site` Elimina sites del disco y la base de datos completamente
  * `--root-login`
  * `--root-password`
* `bench set-config [key] [value]`   Agrega valores clave-valor al archivo de configuración del site
* `bench console`   Abre una consola de IPython en el virtualenv del bench
* `bench execute`   Ejecuta un método dentro de una aplicación
  * Eg : `bench execute frappe.utils.scheduler.enqueue_scheduler_events`
* `bench mysql`  Abre una consola SQL
* `bench run-tests`  Ejecuta las pruebas
  * `--app` Nombre de la aplicación
  * `--doctype` Especificar el DocType para cual correr las pruebas
  * `--test` Pruebas específicas
  * `--module` Ejecutar un módulo con pruebas en específico
  * `--profile` Ejecutar un Python profiler en las pruebas
* `bench disable-production`  Desactiva el entorno de producción


###Programador
* `bench enable-scheduler` - Habilita el Programador que ejecutará las tareas programadas
* `bench doctor` - Obtener informaciones de diagnóstico sobre los background workers
* `bench show-pending-jobs`- Obtener las tareas pendientes
* `bench purge-jobs` - Eliminar todas las tareas pendientes
