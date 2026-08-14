# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE
"""ASGI entry point: ``uvicorn frappe.asgi:application``.

Realtime answers "/socket.io/", the web app answers the other paths. Set
FRAPPE_SERVE_ASSETS to also send /assets and /files, as when there is no proxy.
"""

import os

from a2wsgi import WSGIMiddleware

from frappe.app import application as wsgi_application
from frappe.app import application_with_statics
from frappe.realtime.config import get_config as get_socketio_config
from frappe.realtime.server import RealtimeServer
from frappe.utils.data import sbool

# The number of concurrent web requests. The default of a2wsgi is 10.
DEFAULT_WEB_THREADS = 16
web_threads = int(os.environ.get("FRAPPE_WEB_THREADS") or DEFAULT_WEB_THREADS)

if sbool(os.environ.get("FRAPPE_SERVE_ASSETS", False)):
	wsgi_application = application_with_statics()

socketio_config = get_socketio_config(embedded=True)
application = RealtimeServer(
	socketio_config, other_asgi_app=WSGIMiddleware(wsgi_application, workers=web_threads)
).app
