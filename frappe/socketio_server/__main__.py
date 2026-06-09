"""Entrypoint: python -m frappe.socketio_server

Listens on socketio_uds (if set) or socketio_python_port (default 9001) from
common_site_config.json. Environment overrides: FRAPPE_SOCKETIO_UDS,
FRAPPE_SOCKETIO_PORT.
"""

import uvicorn

from frappe.socketio_server import bench_conf


def main():
	conf = bench_conf()
	kwargs = {"lifespan": "on"}
	if uds := conf.get("socketio_uds"):
		kwargs["uds"] = uds
	else:
		kwargs["host"] = "0.0.0.0"
		kwargs["port"] = int(conf.get("socketio_python_port") or 9001)
	uvicorn.run("frappe.socketio_server.server:asgi_app", **kwargs)


if __name__ == "__main__":
	main()
