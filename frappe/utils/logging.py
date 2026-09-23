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

import re
from pathlib import Path

import frappe
from frappe.database.sqlite.database import SQLiteDatabase
from frappe.model.document import Document

# An optionally table-qualified column, with an optional sort direction: `creation desc`,
# "`tabError Log`.`creation` desc", `creation` -- the shapes the list view and
# `frappe.get_all` actually send. Anything else is ignored rather than guessed at.
#
# This is also the only validation standing between a caller-supplied field name and the
# query: both virtual-DocType dispatchers (`frappe.model.db_query` and
# `frappe.model.qb_query`) hand off to the controller *before* they sanitise fields, and
# the query builder does not escape a field name's quote characters. Keep the `\w+` -- it
# is what stops a crafted `fields` entry from adding SQL of its own.
_FIELD_REF_PATTERN = re.compile(
	r"^\s*(?:[`\"]?tab[^`\"]+[`\"]?\.)?[`\"]?(?P<field>\w+)[`\"]?(?:\s+(?P<direction>asc|desc))?\s*$",
	flags=re.IGNORECASE,
)

#: Basename of the log database, stored as `<site>/logs/<LOG_DB_NAME>.db`.
LOG_DB_NAME = "logs"


class LogDatabase(SQLiteDatabase):
	"""The site's log database.

	Identical to :class:`~frappe.database.sqlite.database.SQLiteDatabase` apart from
	where the file lives: the base class keeps site databases in `<site>/db/`, while
	log data belongs in `<site>/logs/` next to the site's other log output.
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
	elif not frappe.in_test:
		# A console, a patch or a `bench execute`: `frappe.destroy` closes `frappe.db` but
		# knows nothing about this connection, so fall back to interpreter shutdown.
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


class LogDocument(Document):
	"""Base controller for log DocTypes that store their rows in the log database.

	Log DocTypes are declared `is_virtual`, which tells the framework it owns no table
	for them in the site's primary database, and routes persistence and listing through
	the controller. This class implements that contract against :func:`get_log_db`,
	so a log DocType only has to subclass it.

	Writes commit immediately on the log connection. That is the point of the design:
	a record of a failure has to outlive the primary transaction that failed.
	"""

	# ============ instance methods ============

	def db_insert(self, *args, **kwargs):
		"""Insert this document into the log database."""
		from frappe.model.naming import set_new_name

		if not self.name:
			set_new_name(self)

		d = self.get_valid_dict(convert_dates_to_str=True, ignore_virtual=True)

		qb, table = log_table(self.doctype)
		run_log_query(qb.into(table).columns(*d.keys()).insert(*d.values()))
		get_log_db().commit()

		self.set("__islocal", False)

	def db_update(self, *args, **kwargs):
		"""Update this document in the log database."""
		if self.get("__islocal") or not self.name:
			self.db_insert()
			return

		d = self.get_valid_dict(convert_dates_to_str=True, ignore_virtual=True)

		# `name` addresses the row rather than being updated.
		name = d.pop("name")

		qb, table = log_table(self.doctype)
		query = qb.update(table)

		for fieldname, value in d.items():
			query = query.set(table[fieldname], value)

		run_log_query(query.where(table.name == name))
		get_log_db().commit()

	def db_set(self, fieldname, value=None, update_modified=True, notify=False, commit=False):
		"""Write specific fields straight to the log database.

		`Document.db_set` goes through `frappe.db.set_value`, which targets the primary
		database -- where a log DocType has no table. The field handling, `modified` bump and
		`before_change` / `on_change` hooks are kept identical; only the UPDATE moves.

		`commit` is accepted for signature compatibility but ignored: the log connection is
		committed here regardless, and committing the primary transaction is not this
		method's business.
		"""
		if isinstance(fieldname, dict):
			self.update(fieldname)
		else:
			self.set(fieldname, value)

		if update_modified and (self.doctype, self.name) not in frappe.flags.currently_saving:
			self.set("modified", frappe.utils.now())
			self.set("modified_by", frappe.session.user)

		if not self.get_doc_before_save():
			self.load_doc_before_save()

		self.run_method("before_change")

		if self.name is None:
			return

		columns = list(fieldname) if isinstance(fieldname, dict) else [fieldname]
		if update_modified:
			columns += ["modified", "modified_by"]

		qb, table = log_table(self.doctype)
		query = qb.update(table)

		for column in columns:
			query = query.set(table[column], self.get(column))

		run_log_query(query.where(table.name == self.name))
		get_log_db().commit()

		self.run_method("on_change")

		if notify:
			self.notify_update()

	def load_from_db(self):
		"""Populate this document from its row in the log database."""
		qb, table = log_table(self.doctype)

		rows = run_log_query(
			qb.from_(table).select(table.star).where(table.name == self.name),
			as_dict=True,
		)

		if not rows:
			raise frappe.DoesNotExistError(doctype=self.doctype)

		# Bypass Document.__init__, which would try to load the document again.
		super(Document, self).__init__(rows[0])

	def delete(self, *args, **kwargs):
		"""Delete this document from the log database."""
		qb, table = log_table(self.doctype)

		run_log_query(qb.from_(table).where(table.name == self.name).delete())
		get_log_db().commit()

	# ============ class/static methods ============

	@staticmethod
	def get_list(
		doctype: str,
		filters=None,
		fields=None,
		order_by=None,
		group_by=None,
		as_list=False,
		start=None,
		offset=None,
		limit_start=None,
		page_length=None,
		limit=None,
		limit_page_length=None,
		**kwargs,
	):
		"""Return a page of log rows, for the list view and `frappe.get_all`.

		Both spellings of the pagination arguments are accepted because the two virtual
		DocType dispatchers disagree: `frappe.model.qb_query` sends `start`/`page_length`,
		while `frappe.model.db_query` forwards its own `__dict__` and so sends
		`limit_start`/`limit_page_length`. Declaring only one pair would silently ignore
		paging from the other caller.
		"""
		query = _build_log_query(doctype, filters)
		table = query._from[0]

		query = query.select(*_select_terms(table, fields))

		# Dashboard charts aggregate over a log DocType -- `{"COUNT": "*"}` grouped by
		# `creation` -- so grouping has to survive the trip through this controller. Without
		# it the chart receives ungrouped rows and misreads them as its (date, value) pairs.
		if group_by and (grouping := _FIELD_REF_PATTERN.match(str(group_by))):
			query = query.groupby(table[grouping.group("field")])

		if order_by and (ordering := _parse_order_by(table, order_by)):
			query = query.orderby(ordering[0], order=ordering[1])

		requested = _first_given(page_length, limit, limit_page_length)
		# `0` is Frappe's "no limit" (see frappe.get_all); absent means the usual page.
		if requested is None:
			requested = 20

		if frappe.utils.cint(requested):
			query = query.limit(frappe.utils.cint(requested))

		if start_at := frappe.utils.cint(_first_given(start, offset, limit_start) or 0):
			query = query.offset(start_at)

		# `as_list` callers index rows positionally, so they must not get dicts back.
		return run_log_query(query, as_dict=not as_list)

	@staticmethod
	def get_count(doctype: str, filters=None, **kwargs) -> int:
		"""Return the total number of matching log rows."""
		from frappe.query_builder.functions import Count

		result = run_log_query(_build_log_query(doctype, filters).select(Count("*")))

		return frappe.utils.cint(result[0][0]) if result else 0

	@staticmethod
	def get_stats(**kwargs):
		"""Return sidebar stats -- always empty."""
		return {}


def ensure_log_table(doctype: str) -> None:
	"""Create `doctype`'s table in the log database if it is not there yet.

	Log DocTypes are virtual, so `frappe.database.schema.DBTable.sync` deliberately skips
	them and nothing else creates their table. `SQLiteTable` cannot be reused here because it
	issues its DDL through `frappe.db`, which must keep pointing at the primary database.

	Columns come from the DocType's own meta and the log connection's `type_map`, so the table
	matches what `get_valid_dict` will hand to :meth:`LogDocument.db_insert`. Creation is
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


def _first_given(*values):
	"""Return the first argument that was actually supplied, or None."""
	for value in values:
		if value is not None:
			return value

	return None


def log_table(doctype: str):
	"""Return `(builder, table)` for a log DocType's table, creating the table if needed.

	The SQLite dialect is requested explicitly instead of using `frappe.qb`, which is
	bound to the site's primary backend.

	Every query against a log DocType is built from here, so this is where the table is
	guaranteed to exist. Doing it in the individual callers instead would mean a retention
	sweep, a "clear all" or a stats query that happens to run before anything was ever
	logged would hit a table that does not exist yet.
	"""
	from frappe.query_builder.utils import get_query_builder

	ensure_log_table(doctype)

	qb = get_query_builder("sqlite")
	return qb, qb.DocType(doctype)


def run_log_query(query, **kwargs):
	"""Execute a Query Builder query on the log database.

	`Database.sql` walks a Query Builder object itself, so the query arrives with its values
	bound rather than inlined -- the same preparation `QueryBuilder.run` performs, except
	`run` is wired to `frappe.local.db` and so would send this to the primary database.
	Naming the connection here is what keeps log queries on `logs.db`.

	The named placeholders the walk emits are translated to sqlite3's own named style by
	`SQLiteDatabase.execute_query`, so nothing has to be adapted here.
	"""
	return get_log_db().sql(query, **kwargs)


def is_log_doctype(doctype: str) -> bool:
	"""Return True if `doctype` keeps its rows in the log database.

	Code that would otherwise reach for `frappe.db` -- the backup generator, the log
	retention command -- uses this to tell a log DocType apart from an ordinary one,
	because a log DocType owns no table in the site's primary database.
	"""
	from frappe.model.base_document import get_controller

	try:
		return issubclass(get_controller(doctype), LogDocument)
	except Exception:
		# An unknown or uninstalled DocType has no controller, and so is not a log DocType.
		return False


def count_logs(doctype: str, filters=None) -> int:
	"""Return how many rows of `doctype` match `filters`.

	The log database's answer to `frappe.db.count`, which cannot serve a log DocType:
	it builds its query straight from `frappe.qb`, bypassing the virtual-DocType
	dispatch that `frappe.get_all` goes through.
	"""
	return LogDocument.get_count(doctype, filters)


def log_exists(doctype: str, filters=None) -> str | None:
	"""Return the name of one row of `doctype` matching `filters`, or None.

	The log database's answer to `frappe.db.exists`.
	"""
	rows = LogDocument.get_list(doctype, filters=filters, fields=["name"], page_length=1)

	return rows[0]["name"] if rows else None


def delete_logs(doctype: str, filters=None) -> None:
	"""Delete every row of `doctype` matching `filters` and commit the log connection.

	The log database's answer to `frappe.db.delete`. Passing no filters clears the table.
	"""
	run_log_query(_build_log_query(doctype, filters).delete())
	get_log_db().commit()


def _build_log_query(doctype: str, filters=None):
	"""Start a SELECT against `doctype`'s log table, with `filters` applied."""
	from frappe.database.operator_map import OPERATOR_MAP
	from frappe.types.filter import Filters

	qb, table = log_table(doctype)
	query = qb.from_(table)

	if filters is None:
		return query

	if not isinstance(filters, Filters):
		filters = Filters(filters, doctype=doctype)

	for f in filters:
		operation = OPERATOR_MAP.get(f.operator.casefold())

		if operation is None:
			frappe.throw(frappe._("Unsupported filter operator for log DocTypes: {0}").format(f.operator))

		# A filter key is caller-supplied and arrives unsanitised, exactly like a `fields`
		# entry -- see :data:`_FIELD_REF_PATTERN`. It is rejected rather than dropped: a
		# dropped filter silently widens the result set, and `delete_logs` builds its DELETE
		# from this same function, where a dropped predicate would clear the whole table.
		field = _FIELD_REF_PATTERN.match(f.fieldname)

		if not field:
			frappe.throw(frappe._("Invalid filter field for log DocTypes: {0}").format(f.fieldname))

		query = query.where(operation(table[field.group("field")], f.value))

	return query


def _select_terms(table, fields) -> list:
	"""Turn the `fields` argument into query-builder select terms.

	Handles the two spellings `frappe.get_all` accepts: a plain column name, and an
	aggregate written as a dict (`{"COUNT": "*"}`). Entries that match neither are dropped
	rather than guessed at -- see :data:`_FIELD_REF_PATTERN` for why unrecognised strings
	must never reach the query. Dropping everything falls back to `name`, so a caller still
	gets rows rather than a syntax error.
	"""
	if not fields:
		return [table.name]

	if isinstance(fields, str):
		fields = [fields]

	terms = []

	for field in fields:
		if isinstance(field, dict):
			if term := _aggregate_term(table, field):
				terms.append(term)

		elif isinstance(field, str) and (match := _FIELD_REF_PATTERN.match(field)):
			terms.append(table[match.group("field")])

	return terms or [table.name]


def _aggregate_term(table, field: dict):
	"""Return a select term for an aggregate field like `{"COUNT": "*"}` or `{"SUM": "qty"}`.

	The dict spelling is what `frappe.get_all` documents for SQL functions (see
	`FUNCTION_MAPPING` in `frappe.database.query`); supported here are the aggregates a log
	DocType has a use for. Anything else returns None and is dropped by :func:`_select_terms`.
	"""
	from frappe.query_builder.functions import Avg, Count, Max, Min, Sum

	supported = {"COUNT": Count, "SUM": Sum, "AVG": Avg, "MIN": Min, "MAX": Max}

	for name, argument in field.items():
		function = supported.get(str(name).upper())

		if function is None:
			continue

		if argument == "*":
			return function("*")

		if isinstance(argument, str) and (match := _FIELD_REF_PATTERN.match(argument)):
			column = match.group("field")

			# `{"SUM": "1"}` is how a chart with no value field asks for a plain row count:
			# the argument is a literal, not a column, and `table["1"]` would be nonsense.
			if not column.isdigit():
				return function(table[column])

		number = _as_number(argument)

		return function(argument if number is None else number)

	return None


def _as_number(value):
	"""Return `value` as an `int` or `float` if it is one, else None.

	A numeric argument has to reach the query as a number: `SUM("1")` would make SQLite
	sum a string literal, where `SUM(1)` counts rows, which is what the caller meant.
	"""
	if isinstance(value, bool):
		return None

	if isinstance(value, int | float):
		return value

	try:
		number = float(value)
	except (TypeError, ValueError):
		return None

	return int(number) if number.is_integer() else number


def _parse_order_by(table, order_by: str):
	"""Return `(Field, Order)` for a simple `field [asc|desc]` clause, or None."""
	from pypika import Order

	match = _FIELD_REF_PATTERN.match(order_by)

	if not match:
		return None

	direction = (match.group("direction") or "asc").casefold()

	return table[match.group("field")], (Order.desc if direction == "desc" else Order.asc)
