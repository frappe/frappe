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

# `creation desc`, "`tabError Log`.`creation` desc", `creation` -- the shapes the
# list view and `frappe.get_all` actually send. Anything else is ignored rather
# than guessed at.
_ORDER_BY_PATTERN = re.compile(
	r"^\s*(?:[`\"]?tab[^`\"]+[`\"]?\.)?[`\"]?(?P<field>\w+)[`\"]?(?:\s+(?P<direction>asc|desc))?\s*$",
	flags=re.IGNORECASE,
)

_NAMED_PARAMETER_PATTERN = re.compile(r"%\((?P<name>\w+)\)s")

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
	reuses one connection, and is released by :func:`close_log_db` when that request
	or job ends.

	This is a second, independent connection -- it does not replace `frappe.db`, and
	callers are responsible for committing their own writes on it.
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

		fields = _select_fields(fields)
		query = query.select(*(table[f] for f in fields))

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

		return run_log_query(query, as_dict=True)

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
	"""Render a Query Builder query and execute it on the log database.

	`walk()` returns SQL containing named Frappe placeholders and a parameter mapping,
	without executing anything -- the same pattern `frappe.desk.reportview.get_count`
	uses -- so the statement can be handed to the log database rather than to whatever
	`frappe.db` happens to be. The placeholders are converted to positional `%s` first;
	see :func:`_as_positional_params`.

	The resulting values are then handled by SQLiteDatabase.sql(), which converts
	Frappe's `%s` placeholders to SQLite's `?` placeholders and performs normal
	parameter binding.
	"""
	sql, params = query.walk()
	sql, values = _as_positional_params(sql, params)

	return get_log_db().sql(sql, values, **kwargs)


def _as_positional_params(sql: str, params):
	"""Convert named Query Builder parameters to positional parameters.

	Query Builder's `walk()` produces SQL with named placeholders plus a mapping:

		('INSERT INTO "tabError Log" ("name","error") VALUES (%(param1)s,%(param2)s)',
		 {"param1": "EL-1", "param2": "boom"})

	`SQLiteDatabase.execute_query` only binds parameters natively when it is handed a
	sequence -- it rewrites `%s` to sqlite3's `?` and passes the values to the driver.
	Given a dict it instead quotes each value and interpolates it into the statement,
	which binds nothing and mutates the caller's dict. So the placeholders are rewritten
	to `%s` here and the values collected into a tuple.

	The values are taken verbatim: `walk()` stores the raw Python value, not a quoted SQL
	literal, so unwrapping quotes here would silently mangle any log message that happens
	to begin and end with one -- `'NoneType' object has no attribute 'name'` being the
	obvious example.

	The values are collected according to placeholder order in the SQL rather than
	dictionary order.
	"""
	if not isinstance(params, dict):
		return sql, params

	values = []

	def replace_parameter(match):
		name = match.group("name")

		if name not in params:
			raise frappe.ValidationError(frappe._("Missing query parameter: {0}").format(name))

		values.append(params[name])
		return "%s"

	sql = _NAMED_PARAMETER_PATTERN.sub(replace_parameter, sql)

	return sql, tuple(values)


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

		query = query.where(operation(table[f.fieldname], f.value))

	return query


def _select_fields(fields) -> list[str]:
	"""Normalise the `fields` argument to a plain list of column names."""
	if not fields:
		return ["name"]

	if isinstance(fields, str):
		fields = [fields]

	names = []

	for field in fields:
		if not isinstance(field, str):
			continue

		if match := _ORDER_BY_PATTERN.match(field):
			names.append(match.group("field"))

	return names or ["name"]


def _parse_order_by(table, order_by: str):
	"""Return `(Field, Order)` for a simple `field [asc|desc]` clause, or None."""
	from pypika import Order

	match = _ORDER_BY_PATTERN.match(order_by)

	if not match:
		return None

	direction = (match.group("direction") or "asc").casefold()

	return table[match.group("field")], (Order.desc if direction == "desc" else Order.asc)
