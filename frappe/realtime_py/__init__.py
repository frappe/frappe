# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE
"""Standalone Python Socket.IO realtime server.

Replaces the Node.js Socket.IO process. Runs as a separate gevent process;
see ``frappe/realtime_py/server.py`` for the entrypoint.
"""

from frappe.realtime_py.registry import realtime
from frappe.realtime_py.socket import Socket

__all__ = ["Socket", "realtime"]
