# Background Services

Servicios Externos
-----------------

	* MariaDB (Base de datos)
	* Redis (Caché y background workers)
	* nginx (para producción)
	* supervisor (para producción)

Procesos de Frappé
----------------


* Servidor WSGI

	* El servidor WSGI es responsable de responder a las peticiones HTTP.
	En entornos de desarrollo (`bench serve` o `bench start`), El servidor WSGI Werkzeug es usado y en producción,
	se usa gunicorn (automáticamente configurado en supervisor)

* Procesos de Redis Worker

	* Los procesos de Celery se encargan de ejecutar tareas en background en Frappé.
	Estos procesos son iniciados automáticamente cuando se ejecuta el comando `bench start` y
	para producción se configuran en las configuraciones de supervisor.

* Procesos Scheduler

	* Los procesos del Scheduler programan la lista de tareas programadas en Frappé.
	Este proceso es iniciado automáticamente cuando se ejecuta el comando `bench start` y
	para producción se configuran en las configuraciones de supervisor.
