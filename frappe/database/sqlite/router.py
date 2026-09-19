# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

"""Routing between the site's primary database and the SQLite side store.

`frappe.db` is a thread-local proxy over `frappe.local.db`, so pointing that name at a
different connection reroutes every downstream caller -- Document, Meta, DatabaseQuery,
the Query Builder and the schema machinery all read the global rather than taking a
handle. That is exactly how `frappe.connect_replica` / `frappe.read_only` already swap in
a read replica, and :class:`use_sqlite_db` below follows the same shape.

Transaction boundaries between the two stores are independent: the side store commits
alongside the primary as a best-effort mirror, but a write spanning both is *not* atomic.
"""

from contextlib import nullcontext

import frappe


def get_sqlite_db():
	"""Return the connected side-store handle for this thread, creating it on first use."""
	sqlite_db = getattr(frappe.local, "sqlite_db", None)

	if sqlite_db is None:
		from frappe.database.sqlite.side_database import SQLiteSideDatabase

		sqlite_db = SQLiteSideDatabase()
		sqlite_db.connect()
		frappe.local.sqlite_db = sqlite_db

	_mirror_primary_transaction(sqlite_db)

	return sqlite_db


def close_sqlite_db():
	"""Close the side-store connection if one was opened. Called from frappe.destroy()."""
	sqlite_db = getattr(frappe.local, "sqlite_db", None)
	if sqlite_db is not None:
		sqlite_db.close()
		frappe.local.sqlite_db = None
		frappe.local.sqlite_txn_mirrored = False


def _mirror_primary_transaction(sqlite_db):
	"""Commit/rollback the side store whenever the primary database does.

	Best-effort only -- these are two engines and two commits, so a crash between them
	can leave the stores disagreeing. The intent is that an aborted request doesn't leave
	a half-written row behind, not that the pair is atomic.

	The hooks are one-shot and re-armed lazily on the next `get_sqlite_db()` -- that is, the
	next time something actually touches the side store. Re-arming from inside the callback
	would hang: `CallbackManager.run()` drains its queue with `while self._functions`, so a
	callback that re-registers itself never lets the loop finish.

	Nothing is lost by waiting: if no swap happens before the next commit, nothing was written
	to the side store for that commit to mirror.
	"""
	primary = getattr(frappe.local, "db", None)

	if primary is None or primary is sqlite_db:
		return

	if getattr(frappe.local, "sqlite_txn_mirrored", False):
		return

	def on_commit():
		frappe.local.sqlite_txn_mirrored = False
		sqlite_db.commit()

	def on_rollback():
		frappe.local.sqlite_txn_mirrored = False
		sqlite_db.rollback()

	primary.before_commit.add(on_commit)
	primary.after_rollback.add(on_rollback)
	frappe.local.sqlite_txn_mirrored = True


def is_sqlite_doctype(doctype: str) -> bool:
	"""Return True if the DocType stores its rows in the SQLite side store.

	Answered from the cached DocType listing rather than from Meta. Building Meta issues
	`frappe.db` calls, which consult this function to pick a store -- going through Meta
	would recurse. The listing is a single cached query and a set membership test.
	"""
	return isinstance(doctype, str) and doctype in set(get_sqlite_doctypes())


def storage_for(doctype: str):
	"""Return the context manager that selects the store owning `doctype`.

	`nullcontext` for everything in the primary database, so the common path adds one set
	lookup and nothing else.
	"""
	return use_sqlite_db() if is_sqlite_doctype(doctype) else nullcontext()


def get_sqlite_doctypes() -> list[str]:
	"""Return every DocType backed by the SQLite side store.

	`tabDocType` always lives in the primary database, so the lookup is pinned there --
	this is consulted from inside an active swap (to attribute a statement to a store),
	when `frappe.db` points at the side store instead.
	"""

	def _fetch():
		db = getattr(frappe.local, "sqlite_primary_db", None) or frappe.local.db
		if not db.has_column("DocType", "use_sqlite"):
			return []
		# Raw SQL on the pinned handle: the ORM helpers resolve `frappe.local.db` and
		# `frappe.local.qb` internally, which is precisely what must not be followed here.
		return db.sql("SELECT `name` FROM `tabDocType` WHERE `use_sqlite` = 1", pluck=True) or []

	return frappe.cache.get_value("sqlite_doctypes", _fetch) or []


def get_sqlite_tables() -> set[str]:
	"""Return the `tab` table names owned by the SQLite side store."""
	return {f"tab{doctype}" for doctype in get_sqlite_doctypes()}


def clear_sqlite_doctype_cache():
	"""Invalidate the SQLite-backed DocType listing. Called when a DocType is saved."""
	frappe.cache.delete_value("sqlite_doctypes")


class use_sqlite_db:
	"""Point `frappe.db` and `frappe.qb` at the SQLite side store for the duration of a block.

	Reentrant: nesting is a no-op, so a `db_update` called from inside `db_insert` doesn't
	restore the primary connection halfway through.

	Both names have to move together -- `frappe.database.query.Engine` reads `frappe.local.qb`
	for the dialect and `frappe.local.db.db_type` for backend branching, so swapping only the
	connection would emit MariaDB SQL against SQLite.
	"""

	__slots__ = ("_previous_db", "_previous_qb", "_swapped")

	def __enter__(self):
		# Resolve the owned-table set while the primary connection is still in place, so the
		# statement router never has to reach for `tabDocType` from inside the side store.
		get_sqlite_tables()

		sqlite_db = get_sqlite_db()

		if getattr(frappe.local, "db", None) is sqlite_db:
			self._swapped = False
			return sqlite_db

		from frappe.query_builder.utils import get_query_builder

		self._previous_db = frappe.local.db
		self._previous_qb = frappe.local.qb
		self._swapped = True

		frappe.local.sqlite_primary_db = self._previous_db
		frappe.local.db = sqlite_db
		frappe.local.qb = get_query_builder("sqlite")

		return sqlite_db

	def __exit__(self, exc_type, exc_value, traceback):
		if self._swapped:
			frappe.local.db = self._previous_db
			frappe.local.qb = self._previous_qb
			frappe.local.sqlite_primary_db = None

		return False


class use_primary_db:
	"""Restore `frappe.db` and `frappe.qb` to the primary database inside an active swap.

	The inverse of :class:`use_sqlite_db`. Needed when the side store has to hand a whole
	operation back to the primary rather than a single statement -- `get_tables` and friends
	are implemented per backend and re-enter through `frappe.local.db`, so handing over the
	connection object alone would still run the body against SQLite.

	A no-op when no swap is active.
	"""

	__slots__ = ("_previous_db", "_previous_qb", "_primary", "_swapped")

	def __enter__(self):
		self._primary = getattr(frappe.local, "sqlite_primary_db", None)
		self._swapped = self._primary is not None and self._primary is not frappe.local.db

		if not self._swapped:
			return frappe.local.db

		from frappe.query_builder.utils import get_query_builder

		self._previous_db = frappe.local.db
		self._previous_qb = frappe.local.qb

		frappe.local.db = self._primary
		frappe.local.qb = get_query_builder(self._primary.db_type)
		frappe.local.sqlite_primary_db = None

		return self._primary

	def __exit__(self, exc_type, exc_value, traceback):
		if self._swapped:
			frappe.local.db = self._previous_db
			frappe.local.qb = self._previous_qb
			frappe.local.sqlite_primary_db = self._primary

		return False
