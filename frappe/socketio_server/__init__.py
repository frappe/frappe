"""Python implementation of Frappe's realtime (socket.io) server.

Drop-in replacement for apps/frappe/socketio.js. See README.md for
architecture and production notes.
"""

import json
import os
from pathlib import Path


def find_bench_root() -> Path:
	"""Locate the directory containing sites/common_site_config.json —
	FRAPPE_BENCH_ROOT, then cwd and its parents, then this file's location."""
	if env_root := os.environ.get("FRAPPE_BENCH_ROOT"):
		return Path(env_root)
	for candidate in (Path.cwd(), *Path.cwd().parents):
		if (candidate / "sites" / "common_site_config.json").exists():
			return candidate
		if candidate.name == "sites" and (candidate / "common_site_config.json").exists():
			return candidate.parent
	return Path(__file__).resolve().parents[4]


def bench_conf() -> dict:
	"""Read common_site_config.json directly — frappe.get_conf() would pull in
	site init, the wrong dependency at server startup."""
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
	"""redis_queue URL — carries the events channel and the auth secret."""
	return bench_conf().get("redis_queue") or "redis://127.0.0.1:11000"
