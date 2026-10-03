# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See license.txt

"""Dedicated SQLite database for the framework's log DocTypes.

Log records -- errors, page views, access and activity trails -- are written more
often than they are read, and they must survive the transaction they were recorded
in: an Error Log describing a failure is worthless if it rolls back together with
the failure.

Keeping them in their own SQLite database gives both properties for free. The
connection here is entirely separate from `frappe.db`, which continues to serve
every other DocType from the site's primary database. Nothing in this module reads,
assigns to, or otherwise touches `frappe.db` / `frappe.local.db`.
"""

from pathlib import Path

import frappe
from frappe.database.sqlite.database import SQLiteDatabase

#: Basename of the log database, stored as `<site>/logs/<LOG_DB_NAME>.db`.
LOG_DB_NAME = "logs"


class LogDatabase(SQLiteDatabase):
	"""The site's log database.

	Differs from :class:`~frappe.database.sqlite.database.SQLiteDatabase` in two ways.

	Where the file lives: the base class keeps site databases in `<site>/db/`, while log
	data belongs in `<site>/logs/` next to the site's other log output.

	And how it treats transactions. The base class wraps work in a transaction and opens a
	fresh one after every commit, which is right for a site's primary database, where a
	request is one atomic unit. A log database is the opposite: each record is independent
	and has to be durable the moment it is written -- an Error Log describing a failure is
	worthless if it rolls back with the failure. Grouping log writes into a transaction also
	makes them share a lock, so a single write that never reaches its commit holds `logs.db`
	against every other process for the life of the connection. Running in autocommit
	removes both problems: every statement is its own transaction, and no lock outlives the
	statement that took it.
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

	def get_connection(self, read_only: bool = False):
		"""Connect in autocommit mode. See the class docstring."""
		conn = super().get_connection(read_only=read_only)

		# `None` is sqlite3's autocommit: it stops opening an implicit transaction before
		# a write, so each statement commits itself.
		conn.isolation_level = None

		return conn

	def begin(self, *, read_only=False):
		"""No-op: this connection never opens an explicit transaction.

		`SQLiteDatabase.commit` calls `begin` to re-open one straight after committing, which
		would leave the connection permanently mid-transaction and defeat autocommit.
		"""


def get_log_db() -> LogDatabase:
	"""Return the log database handle, connecting on first use.

	The handle is cached on `frappe.local` so a request or job that logs repeatedly
	reuses one connection, and the connection queues its own closure for the end of
	whatever context opened it.

	This is a second, independent connection -- it does not replace `frappe.db`, and
	callers are responsible for committing their own writes on it.
	"""
	log_db = getattr(frappe.local, "log_db", None)

	if log_db is None:
		log_db = LogDatabase()
		log_db.connect()
		frappe.local.log_db = log_db
		_enqueue_connection_closure()

	return log_db


def _enqueue_connection_closure():
	"""Arrange for :func:`close_log_db` to run at the end of the current context.

	Registering here rather than through the `after_request` / `after_job` hooks means the
	cleanup is queued only by the code path that actually opened a connection -- most
	requests never log anything and so never queue it. It also makes a reopen self-healing:
	a connection opened *after* cleanup has already run -- `commit_after_response`
	callbacks log their own failures, well past `after_request` -- queues a fresh closure,
	and `frappe.app.get_after_response_callbacks` drains callbacks added by other callbacks.

	The three contexts mirror `frappe.email.smtp.SMTPServer._enqueue_connection_closure`,
	which solves the same problem for pooled SMTP connections.
	"""
	if frappe.request and hasattr(frappe.request, "after_response"):
		frappe.request.after_response.add(close_log_db)
	elif frappe.job:
		frappe.job.after_job.add(close_log_db)
	else:
		# A console, a patch, a `bench execute` or a test runner: there is no request or job
		# to hang the cleanup on, and `frappe.destroy` closes `frappe.db` without knowing
		# about this connection. `SQLiteDatabase.commit` opens a fresh transaction straight
		# after committing, so a connection left open holds one for the life of the process
		# and every other writer queues behind it. Fall back to interpreter shutdown.
		import atexit

		atexit.register(close_log_db)


def close_log_db():
	"""Close the log database connection if this context opened one.

	Queued by :func:`_enqueue_connection_closure`. Safe to call more than once, and a no-op
	when nothing was logged.
	"""
	log_db = getattr(frappe.local, "log_db", None)

	if log_db is not None:
		log_db.close()
		frappe.local.log_db = None


def ensure_log_table(doctype: str) -> None:
	"""Create `doctype`'s table in the log database if it is not there yet.

	Log DocTypes are virtual, so `frappe.database.schema.DBTable.sync` deliberately skips
	them and nothing else creates their table. `SQLiteTable` cannot be reused here because it
	issues its DDL through `frappe.db`, which must keep pointing at the primary database.

	Columns come from the DocType's own meta and the log connection's `type_map`, so the table
	matches what `get_valid_dict` will hand to :meth:`SQLiteLogDocument.db_insert`. Creation is
	one-shot per process: the check is cached on `frappe.local`.
	"""
	created = getattr(frappe.local, "log_tables_ready", None)

	if created is None:
		created = frappe.local.log_tables_ready = set()

	if doctype in created:
		return

	log_db = get_log_db()
	table = f"tab{doctype}"
	meta = frappe.get_meta(doctype)

	definitions = [
		"`name` TEXT PRIMARY KEY",
		"`creation` TIMESTAMP",
		"`modified` TIMESTAMP",
		"`modified_by` TEXT",
		"`owner` TEXT",
		"`docstatus` INTEGER NOT NULL DEFAULT 0",
		"`idx` INTEGER NOT NULL DEFAULT 0",
	]

	for column in meta.get_valid_columns():
		if column in log_db.DEFAULT_COLUMNS:
			continue

		field = meta.get_field(column)
		column_type = log_db.type_map.get(field.fieldtype, ("TEXT", None))[0] if field else "TEXT"
		definitions.append(f"`{column}` {column_type}")

	# `IF NOT EXISTS` rather than a `get_tables()` probe: that helper caches under the
	# site-global `db_tables` key, which the primary connection also uses, so asking it here
	# would overwrite the primary's cached table list.
	log_db.sql_ddl("CREATE TABLE IF NOT EXISTS `{}` ({})".format(table, ", ".join(definitions)))
	log_db.sql_ddl(f"CREATE INDEX IF NOT EXISTS `{table}_creation_idx` ON `{table}` (`creation`)")

	created.add(doctype)


def log_table(doctype: str):
	from frappe.query_builder.utils import get_query_builder

	ensure_log_table(doctype)

	qb = get_query_builder("sqlite")
	return qb, qb.DocType(doctype)


def is_log_doctype(doctype: str) -> bool:
	"""Return True if `doctype` keeps its rows in the log database.

	Code that would otherwise reach for `frappe.db` -- the backup generator, the log
	retention command -- uses this to tell a log DocType apart from an ordinary one,
	because a log DocType owns no table in the site's primary database.
	"""
	from frappe.model.base_document import get_controller
	from frappe.utils.sqlite_document import SQLiteLogDocument

	try:
		return issubclass(get_controller(doctype), SQLiteLogDocument)
	except ImportError:
		# The one expected failure: an unknown or uninstalled DocType has no controller to
		# import, and so is not a log DocType. `import_controller` raises `ImportError` for
		# every such case, and `ModuleNotFoundError` is a subclass of it.
		#
		# Anything else is a real fault -- an invalid class override, for instance, which
		# `import_controller` reports with `frappe.throw` -- and must not be quietly
		# reclassified as an ordinary DocType.
		return False
