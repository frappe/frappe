# Background Services

External services
-----------------

	* MariaDB (Datastore for frappe)
	* Redis (Queue for frappe background workers and caching)
	* nginx (for production deployment)
	* supervisor (for production deployment)

Frappé Processes
----------------


* WSGI Server

	* The WSGI server is responsible for responding to the HTTP requests to
	frappe. In development scenario (`bench serve` or `bench start`), the
	Werkzeug WSGI server is used and in production, gunicorn (automatically
	configured in supervisor) is used.

* Redis Worker Processes

	* The Celery worker processes execute background jobs in the Frappé system.
	These processes are automatically started when `bench start` is run and
	for production are configured in supervisor configuration.

* Scheduler Process

	* The Scheduler process schedules enqeueing of scheduled jobs in the
	Frappé system. This process is automatically started when `bench start` is
	run and for production are configured in supervisor configuration.