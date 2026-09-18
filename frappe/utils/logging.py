# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

"""Dedicated SQLite database for the framework's log DocTypes.

Log records -- errors, page views, access and activity trails -- are written far more
often than they are read, and they must survive the transaction they were recorded in:
an Error Log describing a failure is worthless if it rolls back together with the failure.

Keeping them in their own SQLite database gives both properties for free. The connection
here is entirely separate from `frappe.db`, which continues to serve every other DocType
from the site's primary database. Nothing in this module reads, assigns to, or otherwise
touches `frappe.db` / `frappe.local.db`.
"""

from pathlib import Path

import frappe
from frappe.database.sqlite.database import SQLiteDatabase

#: Basename of the log database, stored as `<site>/logs/<LOG_DB_NAME>.db`.
LOG_DB_NAME = "logs"


class LogDatabase(SQLiteDatabase):
	"""The site's log database.

	Identical to :class:`~frappe.database.sqlite.database.SQLiteDatabase` apart from where
	the file lives: the base class keeps site databases in `<site>/db/`, while log data
	belongs in `<site>/logs/` next to the site's other log output.
	"""

	def __init__(self):
		super().__init__(cur_db_name=LOG_DB_NAME)

	def get_db_path(self) -> Path:
		"""Return `<site>/logs/logs.db`."""
		return Path(frappe.get_site_path()) / "logs" / f"{self.cur_db_name}.db"

	def connect(self):
		# sqlite3 creates the database file on connect, but not its parent directory.
		self.get_db_path().parent.mkdir(parents=True, exist_ok=True)
		super().connect()


def get_log_db() -> LogDatabase:
	"""Return the log database handle, connecting on first use.

	The handle is cached on `frappe.local` so a request or job that logs repeatedly reuses
	one connection, and is released by :func:`close_log_db` when that request or job ends.

	This is a second, independent connection -- it does not replace `frappe.db`, and callers
	are responsible for committing their own writes on it.
	"""
	log_db = getattr(frappe.local, "log_db", None)

	if log_db is None:
		log_db = LogDatabase()
		log_db.connect()
		frappe.local.log_db = log_db

	return log_db


def close_log_db():
	"""Close the log database connection if this request/job opened one.

	Registered on the `after_request` and `after_job` hooks. A no-op when nothing was
	logged, which is the common case.
	"""
	log_db = getattr(frappe.local, "log_db", None)

	if log_db is not None:
		log_db.close()
		frappe.local.log_db = None
