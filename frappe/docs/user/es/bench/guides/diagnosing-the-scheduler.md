# Diagnosing The Scheduler

<!-- markdown -->

En caso que estes experimentando inconvenientes con las tareas programadas, puedes ejecutar varios comandos para diagnosticar el problema.

### `bench doctor`

Esto va a mostrar en la consola lo siguiente en orden:
- El estado del Scheduler por site
- Número de Workers
- Tareas Pendientes


Salida deseada:

	Workers online: 0
	-----None Jobs-----

### `bench --site [site-name] show-pending-jobs`

Esto va a mostrar en la consola lo siguiente en orden:
- Cola
- Tareas dentro de Cola

Salida deseada:

	-----Pending Jobs-----


### `bench purge-jobs`

Esto va a remover todas las tareas programadas de todas las colas.
