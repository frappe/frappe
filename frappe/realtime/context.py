# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE


import logging
from contextlib import contextmanager

logger = logging.getLogger("frappe.realtime")


@contextmanager
def frappe_context(site: str, user: str):
	"""Per-handler Frappe context.

	Opened only for handlers registered with frappe_context=True. Every such event
	pays the full init -> connect -> set_user -> commit/rollback -> destroy cycle and
	forces a DB connection into the realtime process, so use it sparingly; the cheap
	default is the HTTP permission check on Socket.

	The DB connection is forced onto the pure-python PyMySQL driver (see
	server.force_pymysql) — the mysqlclient C extension would stall the gevent hub.
	"""
	import frappe
	from frappe.realtime.server import force_pymysql

	frappe.init(site)
	force_pymysql(frappe.local.conf)
	frappe.connect()
	frappe.set_user(user)  # nosemgrep
	try:
		yield frappe
		frappe.db.commit()  # nosemgrep
	except Exception:
		frappe.db.rollback()
		raise
	finally:
		frappe.destroy()
