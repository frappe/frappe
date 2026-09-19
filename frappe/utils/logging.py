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

		qb, table = _log_table(self.doctype)
		_run_log_query(qb.into(table).columns(*d.keys()).insert(*d.values()))
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

		qb, table = _log_table(self.doctype)
		query = qb.update(table)

		for fieldname, value in d.items():
			query = query.set(table[fieldname], value)

		_run_log_query(query.where(table.name == name))
		get_log_db().commit()

	def load_from_db(self):
		"""Populate this document from its row in the log database."""
		qb, table = _log_table(self.doctype)

		rows = _run_log_query(
			qb.from_(table).select(table.star).where(table.name == self.name),
			as_dict=True,
		)

		if not rows:
			raise frappe.DoesNotExistError(doctype=self.doctype)

		# Bypass Document.__init__, which would try to load the document again.
		super(Document, self).__init__(rows[0])

	def delete(self, *args, **kwargs):
		"""Delete this document from the log database."""
		qb, table = _log_table(self.doctype)

		_run_log_query(
			qb.from_(table).where(table.name == self.name).delete()
		)
		get_log_db().commit()

	# ============ class/static methods ============

	@staticmethod
	def get_list(
		doctype: str,
		filters=None,
		fields=None,
		order_by=None,
		start=0,
		page_length=20,
		**kwargs,
	):
		"""Return a page of log rows, for the list view and `frappe.get_all`."""
		query = _build_log_query(doctype, filters)
		table = query._from[0]

		fields = _select_fields(fields)
		query = query.select(*(table[f] for f in fields))

		if order_by and (ordering := _parse_order_by(table, order_by)):
			query = query.orderby(ordering[0], order=ordering[1])

		query = query.limit(
			frappe.utils.cint(page_length) or 20
		).offset(
			frappe.utils.cint(start)
		)

		return _run_log_query(query, as_dict=True)

	@staticmethod
	def get_count(doctype: str, filters=None, **kwargs) -> int:
		"""Return the total number of matching log rows."""
		from frappe.query_builder.functions import Count

		result = _run_log_query(
			_build_log_query(doctype, filters).select(Count("*"))
		)

		return frappe.utils.cint(result[0][0]) if result else 0

	@staticmethod
	def get_stats(**kwargs):
		"""Return sidebar stats -- always empty."""
		return {}


def _log_table(doctype: str):
	"""Return `(builder, table)` for a log DocType's table.

	The SQLite dialect is requested explicitly instead of using `frappe.qb`, which is
	bound to the site's primary backend.
	"""
	from frappe.query_builder.utils import get_query_builder

	qb = get_query_builder("sqlite")
	return qb, qb.DocType(doctype)


def _run_log_query(query, **kwargs):
	"""Render a Query Builder query and execute it on the log database.

	`walk()` returns SQL containing named Frappe placeholders and a parameter mapping.
	For string values, the current Query Builder stores the SQL-quoted representation
	of the value. Before binding the parameters to SQLite, convert the placeholders
	to positional `%s` placeholders and restore those strings to their actual values.

	The resulting values are then handled by SQLiteDatabase.sql(), which converts
	Frappe's `%s` placeholders to SQLite's `?` placeholders and performs normal
	parameter binding.
	"""
	sql, params = query.walk()
	sql, values = _as_positional_params(sql, params)

	return get_log_db().sql(sql, values, **kwargs)


def _as_positional_params(sql: str, params):
	"""Convert named Query Builder parameters to positional parameters.

	Query Builder's `walk()` produces parameters such as:

		{
			"param1": "'hello'",
			"param2": "'world'"
		}

	The string values are already SQL-quoted. SQLite parameter binding must receive
	the underlying values instead:

		("hello", "world")

	The values are collected according to placeholder order in the SQL rather than
	dictionary order.
	"""
	if not isinstance(params, dict):
		return sql, params

	values = []

	def replace_parameter(match):
		name = match.group("name")

		if name not in params:
			raise frappe.ValidationError(
				frappe._("Missing query parameter: {0}").format(name)
			)

		value = params[name]

		if isinstance(value, str):
			value = _unquote_sql_string(value)

		values.append(value)
		return "%s"

	sql = _NAMED_PARAMETER_PATTERN.sub(replace_parameter, sql)

	return sql, tuple(values)


def _unquote_sql_string(value: str) -> str:
	"""Convert a SQL single-quoted string literal back to its Python string value."""
	if len(value) >= 2 and value.startswith("'") and value.endswith("'"):
		return value[1:-1].replace("''", "'")

	return value


def _build_log_query(doctype: str, filters=None):
	"""Start a SELECT against `doctype`'s log table, with `filters` applied."""
	from frappe.database.operator_map import OPERATOR_MAP
	from frappe.types.filter import Filters

	qb, table = _log_table(doctype)
	query = qb.from_(table)

	if filters is None:
		return query

	if not isinstance(filters, Filters):
		filters = Filters(filters, doctype=doctype)

	for f in filters:
		operation = OPERATOR_MAP.get(f.operator.casefold())

		if operation is None:
			frappe.throw(
				frappe._(
					"Unsupported filter operator for log DocTypes: {0}"
				).format(f.operator)
			)

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

	return table[match.group("field")], (
		Order.desc if direction == "desc" else Order.asc
	)