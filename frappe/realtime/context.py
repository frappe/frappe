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

	Runs on a worker thread, never on the event loop, so a blocking driver is fine.
	force=True is required: frappe.local is a shared mutable dict behind a
	ContextVar, and only init(force=True) rebinds a fresh one for this call.
	"""
	import frappe

	frappe.init(site, force=True)
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
