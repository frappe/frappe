# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Keep tool transaction callbacks inside the tool's savepoint."""

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import uuid4

import frappe
from frappe.utils import CallbackManager

CALLBACK_QUEUES = ("before_commit", "after_commit", "before_rollback", "after_rollback")


@contextmanager
def tool_savepoint() -> Iterator[None]:
	"""Preserve earlier callbacks and run only the failed tool's rollback cleanup."""
	db = frappe.db
	original = {name: getattr(db, name) for name in CALLBACK_QUEUES}
	callbacks = {name: CallbackManager() for name in CALLBACK_QUEUES}
	savepoint = f"mcp_{uuid4().hex}"
	db.savepoint(savepoint)
	for name, queue in callbacks.items():
		setattr(db, name, queue)
	try:
		try:
			yield
		except Exception:
			# SQL savepoint rollback does not run Frappe's rollback callbacks.
			try:
				db.run_after_transaction_callbacks(callbacks["before_rollback"])
				db.rollback(save_point=savepoint)
				db.run_after_transaction_callbacks(callbacks["after_rollback"])
			finally:
				db.release_savepoint(savepoint)
			raise
		else:
			db.release_savepoint(savepoint)
			for name, queue in callbacks.items():
				for callback in queue.cut(0):
					original[name].add(callback)
	finally:
		for name, queue in original.items():
			setattr(db, name, queue)
