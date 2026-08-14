# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE
"""ASGI entry point: the web application of Frappe, and realtime if it is embedded.

    uvicorn frappe.asgi:application

If "socketio_backend" is "python-embedded", the realtime server in this process
answers "/socket.io/", and the web app answers all the other requests. With a
different backend this app is only the web app, and realtime keeps its own process.

Usually nginx sends /assets and /files, thus this app does not. Set
FRAPPE_SERVE_ASSETS to send them from this process, as when there is no proxy.

a2wsgi runs the WSGI app in a thread pool. The program that starts uvicorn
controls the address, the number of workers, the supervision, and the work
directory.
"""

import os

from a2wsgi import WSGIMiddleware

from frappe.app import application as wsgi_application
from frappe.app import application_with_statics
from frappe.realtime.config import get_config as get_socketio_config
from frappe.utils.data import sbool

# The number of concurrent web requests. The default of a2wsgi is 10.
DEFAULT_WEB_THREADS = 16
web_threads = int(os.environ.get("FRAPPE_WEB_THREADS") or DEFAULT_WEB_THREADS)

if sbool(os.environ.get("FRAPPE_SERVE_ASSETS", False)):
	wsgi_application = application_with_statics()

socketio_config = get_socketio_config()
application = WSGIMiddleware(wsgi_application, workers=web_threads)

if socketio_config.embedded:
	from frappe.realtime.server import RealtimeServer

	application = RealtimeServer(socketio_config, other_asgi_app=application).app
