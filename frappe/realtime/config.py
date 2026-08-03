# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE
"""Resolve realtime server config.

Reuses ``frappe.get_common_site_config()`` (the same ``common_site_config.json``
the Node ``node_utils.get_conf`` reads) instead of re-porting the JSON parse.
Config comes only from common_site_config.json / site_config.json — no env vars.

``frappe`` is imported lazily so this module can be imported in tests without a
configured bench, and so import never precedes the gevent monkeypatch in server.py.
"""

from dataclasses import dataclass

# node_utils default
DEFAULT_SOCKETIO_PORT = 9000

# Matches frappe.config._get_site_config fallback; used only if common_site_config.json
# is silent on redis_queue, which should not happen in a real bench.
DEFAULT_REDIS_QUEUE = "redis://127.0.0.1:11311"


@dataclass(frozen=True)
class RealtimeConfig:
	port: int
	redis_queue: str
	uds: str | None = None
	default_site: str | None = None
	developer_mode: bool = False
	webserver_port: int | None = None
	webserver_host: str | None = None


def get_config(sites_path: str | None = None) -> RealtimeConfig:
	"""Build the realtime config from common_site_config.json."""
	import frappe

	sites_path = sites_path or getattr(frappe.local, "sites_path", None) or "sites"
	conf = frappe.get_common_site_config(sites_path=sites_path)

	webserver_port = conf.get("webserver_port")
	return RealtimeConfig(
		port=int(conf.get("socketio_port") or DEFAULT_SOCKETIO_PORT),
		redis_queue=conf.get("redis_queue") or DEFAULT_REDIS_QUEUE,
		uds=conf.get("socketio_uds") or None,
		default_site=conf.get("default_site") or None,
		developer_mode=bool(conf.get("developer_mode")),
		webserver_port=int(webserver_port) if webserver_port else None,
		webserver_host=conf.get("webserver_host") or None,
	)
