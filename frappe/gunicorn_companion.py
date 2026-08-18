# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE
"""Companion processes for the gunicorn companion manager.

Each "run_*" function below is one companion (worker, scheduler, socketio).
They are listed in "companion_workers" in the generated "config/gunicorn.conf.py"
as "frappe.gunicorn_companion:run_*", and take no arguments.

The manager starts each one by forking the already-loaded gunicorn master, so
the companion reuses the master's memory instead of loading its own copy.
"""

import os


def warmup() -> None:
	"""Load the worker code in the master before any companion is forked, so the
	worker and scheduler companions can reuse it instead of loading their own copy.

	Called from the gunicorn "on_starting" hook. Socketio is left out on purpose:
	loading it would pull gevent into the master and break the other companions.
	"""
	import redis
	import rq
	import rq.worker

	try:
		from rq.worker_pool import WorkerPool
	except ImportError:
		pass  # older rq keeps the pool elsewhere; safe to skip here

	import frappe.utils.background_jobs
	import frappe.utils.scheduler


def run_scheduler() -> None:
	"""Run frappe scheduler"""
	from frappe.utils.scheduler import start_scheduler

	start_scheduler()


def run_worker() -> None:
	"""Run one rq worker. Queues come from "FRAPPE_COMPANION_QUEUE" (comma list)."""
	from frappe.utils.background_jobs import start_worker

	queue = os.environ.get("FRAPPE_COMPANION_QUEUE") or None
	start_worker(queue=queue)


def run_worker_pool() -> None:
	"""Run a pool of rq workers. Queues come from "FRAPPE_COMPANION_QUEUE", and
	the number of workers from "FRAPPE_COMPANION_NUM_WORKERS" (default 1)."""
	from frappe.utils.background_jobs import start_worker_pool

	queue = os.environ.get("FRAPPE_COMPANION_QUEUE") or None
	num_workers = int(os.environ.get("FRAPPE_COMPANION_NUM_WORKERS") or 1)
	start_worker_pool(queue=queue, num_workers=num_workers)


def run_socketio() -> None:
	"""Run the realtime (socketio) server. The backend is chosen at runtime.

	If the backend is "python": run in this process. Otherwise: hand off to
	node running "apps/frappe/socketio.js". Either way this runs from the
	bench dir, just like "bench socketio".
	"""
	backend = _socketio_backend()

	if backend == "python":
		from frappe.realtime.server import serve

		serve()
		return

	import shutil

	node = shutil.which("node") or shutil.which("nodejs")
	if not node:
		raise RuntimeError(
			f"Cannot start socketio companion: node not found and socketio_backend is "
			f"{backend!r} (not 'python'). Install node or set socketio_backend to 'python'."
		)
	from frappe.utils import get_bench_path

	os.execv(node, [node, os.path.join(get_bench_path(), "apps", "frappe", "socketio.js")])


def _socketio_backend() -> str:
	"""Read "socketio_backend" from common_site_config. Defaults to "node".

	The "sites/" folder is located from the bench root (via
	"frappe.utils.get_bench_path"), not the current directory. So this reads the
	right file whether bench is run from the bench dir or from inside "sites/".
	"""
	import json

	from frappe.utils import get_bench_path

	path = os.path.join(get_bench_path(), "sites", "common_site_config.json")
	try:
		with open(path) as config_file:  # nosemgrep
			return (json.load(config_file) or {}).get("socketio_backend", "node")
	except (OSError, ValueError):
		return "node"
