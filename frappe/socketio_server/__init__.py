"""Shared helpers for the prototype python-socketio server."""

import json
import os
from pathlib import Path


def bench_conf() -> dict:
	"""Read sites/common_site_config.json directly — mirrors node_utils.get_conf.

	We deliberately do NOT call frappe.get_conf() because it triggers
	frappe.init_site → setup_module_map → reads apps.txt from cwd, which is
	the wrong dependency at server-startup / per-connect time.
	"""
	bench_root = Path(os.environ.get("FRAPPE_BENCH_ROOT", Path.cwd()))
	conf_path = bench_root / "sites" / "common_site_config.json"
	conf: dict = {"socketio_port": 9000, "socketio_python_port": 9001}
	if conf_path.exists():
		conf.update(json.loads(conf_path.read_text()))
	for env_key, conf_key in [
		("FRAPPE_SITE", "default_site"),
		("FRAPPE_REDIS_QUEUE", "redis_queue"),
		("FRAPPE_SOCKETIO_PORT", "socketio_python_port"),
	]:
		if env_key in os.environ:
			conf[conf_key] = os.environ[env_key]
	return conf
