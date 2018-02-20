# Bench Procfile

`bench start` usa [honcho](http://honcho.readthedocs.org) para manejar múltiples procesos en **developer mode**.

### Procesos

Los diversos procesos que se necesitan para correr frappe son:

1. `bench start` - El servidor web.
4. `redis_cache` para cache (general)
5. `redis_queue` para manejar las cosas de los background workers
6. `redis_socketio` como un notificador de notificaciones para actualizaciones en tiempo real desde los background workers
7. `web` para el servidor web de frappe.
7. `socketio` para mensajes en tiempo real.
3. `schedule` para disparar tareas periódicas
3. `worker_*` redis workers para manejar trabajos aíncronos

Opcionalmente, si estas desarrollando en frappe puedes agregar:

`bench watch` para automáticamente construir la aplicación  javascript desk.

### Ejemplo

	redis_cache: redis-server config/redis_cache.conf
	redis_socketio: redis-server config/redis_socketio.conf
	redis_queue: redis-server config/redis_queue.conf
	web: bench serve --port 8000
	socketio: /usr/bin/node apps/frappe/socketio.js
	watch: bench watch
	schedule: bench schedule
	worker_short: bench worker --queue short
	worker_long: bench worker --queue long
	worker_default: bench worker --queue default
