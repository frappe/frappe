# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE
"""ASGI entry point: the Frappe web application, plus realtime when embedded.

    uvicorn frappe.asgi:application

With "socketio_backend" set to "python-embedded", "/socket.io/" is served by the
realtime server in this process and everything else by the web app. Under any
other backend this is the web app alone, and realtime keeps its own process.

/assets and /files are nginx's job, so they are left out; set FRAPPE_SERVE_ASSETS
to serve them from this process instead, as with no proxy in front.

a2wsgi runs the WSGI app in a thread pool. Binding, worker counts, supervision and
the working directory belong to whatever starts uvicorn.
"""

import os

from a2wsgi import WSGIMiddleware

from frappe.app import application as wsgi_application
from frappe.app import application_with_statics
from frappe.realtime.config import get_config as get_socketio_config
from frappe.utils.data import sbool

# Concurrent web requests; a2wsgi would otherwise apply its own default of 10.
DEFAULT_WEB_THREADS = 16
web_threads = int(os.environ.get("FRAPPE_WEB_THREADS") or DEFAULT_WEB_THREADS)

if sbool(os.environ.get("FRAPPE_SERVE_ASSETS", False)):
	wsgi_application = application_with_statics()

socketio_config = get_socketio_config()
application = WSGIMiddleware(wsgi_application, workers=web_threads)

if socketio_config.embedded:
	from frappe.realtime.server import RealtimeServer

	application = RealtimeServer(socketio_config, other_asgi_app=application).app
