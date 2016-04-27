`bench start` uses [honcho](http://honcho.readthedocs.org) to manage multiple processes in **developer mode**.

### Processes

The various process that are needed to run frappe are:

1. `bench start` - the web server
2. celery task queue for background workers (scheduled jobs and other async tasks)
3. celery worker beat to trigger periodic tasks
4. `redis` for caching (general)
5. `redis` for managing queue for background workers
6. `redis` as a message broker for real-time updates / updates from background workers
7. `node` to run `socketio` for real-time messaging.

Optionally if you are developing for frappe you can add:

`bench watch` to automatically build the desk javascript app.

### Sample

	web: bench --site test.erpnext.com serve --port 8001
	redis_async_broker: redis-server config/redis_async_broker.conf
	socketio: node apps/frappe/socketio.js
	workerbeat: sh -c 'cd sites && exec ../env/bin/python -m frappe.celery_app beat -s scheduler.schedule'
	worker: sh -c 'cd sites && exec ../env/bin/python -m frappe.celery_app worker'
	redis_cache: redis-server config/redis_cache.conf
	redis: redis-server
	watch: bench watch