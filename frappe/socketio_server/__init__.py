"""Python implementation of Frappe's realtime (socket.io) server.

Drop-in replacement for ``apps/frappe/socketio.js`` built on python-socketio
and uvicorn. Run with::

	python -m frappe.socketio_server

See README.md in this directory for architecture and production notes.
"""

import json
import os
from pathlib import Path


def find_bench_root() -> Path:
	"""Locate the bench root (the directory containing sites/common_site_config.json).

	Resolution order: FRAPPE_BENCH_ROOT env var, then cwd and its parents
	(covers running from bench root, sites dir, or an app dir), then the
	location of this file (apps/frappe/frappe/socketio_server).
	"""
	if env_root := os.environ.get("FRAPPE_BENCH_ROOT"):
		return Path(env_root)
	for candidate in (Path.cwd(), *Path.cwd().parents):
		if (candidate / "sites" / "common_site_config.json").exists():
			return candidate
		if candidate.name == "sites" and (candidate / "common_site_config.json").exists():
			return candidate.parent
	return Path(__file__).resolve().parents[4]


def bench_conf() -> dict:
	"""Read sites/common_site_config.json directly — mirrors node_utils.get_conf.

	We deliberately do NOT call frappe.get_conf() because it triggers
	frappe.init_site → setup_module_map → reads apps.txt from cwd, which is
	the wrong dependency at server-startup / per-connect time.
	"""
	conf: dict = {"socketio_port": 9000, "socketio_python_port": 9001}
	conf_path = find_bench_root() / "sites" / "common_site_config.json"
	if conf_path.exists():
		conf.update(json.loads(conf_path.read_text()))
	for env_key, conf_key in [
		("FRAPPE_SITE", "default_site"),
		("FRAPPE_REDIS_QUEUE", "redis_queue"),
		("FRAPPE_SOCKETIO_PORT", "socketio_python_port"),
		("FRAPPE_SOCKETIO_UDS", "socketio_uds"),
	]:
		if env_key in os.environ:
			conf[conf_key] = os.environ[env_key]
	return conf


def redis_url() -> str:
	"""URL of the redis_queue instance — carries the `events` pub/sub channel
	and the socketio_auth_secret key, same as the Node implementation."""
	return bench_conf().get("redis_queue") or "redis://127.0.0.1:11000"
