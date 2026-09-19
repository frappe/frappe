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

import re
from pathlib import Path

import frappe
from frappe.database.sqlite.database import SQLiteDatabase
from frappe.model.document import Document

# `creation desc`, "`tabError Log`.`creation` desc", `creation` -- the shapes the list view
# and `frappe.get_all` actually send. Anything else is ignored rather than guessed at.
_ORDER_BY_PATTERN = re.compile(
	r"^\s*(?:[`\"]?tab[^`\"]+[`\"]?\.)?[`\"]?(?P<field>\w+)[`\"]?(?:\s+(?P<direction>asc|desc))?\s*$",
	flags=re.IGNORECASE,
)

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


class LogDocument(Document):
	"""Base controller for log DocTypes that store their rows in the log database.

	Log DocTypes are declared `is_virtual`, which tells the framework it owns no table for
	them in the site's primary database, and routes persistence and listing through the
	controller instead. This class implements that contract -- the
	:class:`frappe.model.virtual_doctype.VirtualDoctype` protocol -- against
	:func:`get_log_db`, so a log DocType only has to subclass it.

	Writes commit immediately on the log connection. That is the point of the design: a
	record of a failure has to outlive the primary transaction that failed.
	"""

	# ============ instance methods ============

	def db_insert(self, *args, **kwargs):
		"""Insert this document into the log database."""
		from frappe.model.naming import set_new_name

		if not self.name:
			set_new_name(self)

		d = self.get_valid_dict(convert_dates_to_str=True, ignore_virtual=True)
		columns = list(d)

		log_db = get_log_db()
		log_db.sql(
			"INSERT INTO `tab{doctype}` ({columns}) VALUES ({values})".format(
				doctype=self.doctype,
				columns=", ".join("`" + c + "`" for c in columns),
				values=", ".join(["%s"] * len(columns)),
			),
			list(d.values()),
		)
		log_db.commit()

		self.set("__islocal", False)

	def db_update(self, *args, **kwargs):
		"""Update this document in the log database."""
		if self.get("__islocal") or not self.name:
			self.db_insert()
			return

		d = self.get_valid_dict(convert_dates_to_str=True, ignore_virtual=True)
		name = d.pop("name")
		columns = list(d)

		log_db = get_log_db()
		log_db.sql(
			"UPDATE `tab{doctype}` SET {values} WHERE `name` = %s".format(
				doctype=self.doctype,
				values=", ".join("`" + c + "`=%s" for c in columns),
			),
			[*d.values(), name],
		)
		log_db.commit()

	def load_from_db(self):
		"""Populate this document from its row in the log database."""
		rows = get_log_db().sql(
			f"SELECT * FROM `tab{self.doctype}` WHERE `name` = %s",
			(self.name,),
			as_dict=True,
		)

		if not rows:
			raise frappe.DoesNotExistError(doctype=self.doctype)

		# Bypass Document.__init__, which would try to load the document again.
		super(Document, self).__init__(rows[0])

	def delete(self, *args, **kwargs):
		"""Delete this document from the log database."""
		log_db = get_log_db()
		log_db.sql(f"DELETE FROM `tab{self.doctype}` WHERE `name` = %s", (self.name,))
		log_db.commit()

	# ============ class/static methods ============

	@staticmethod
	def get_list(doctype: str, filters=None, fields=None, order_by=None, start=0, page_length=20, **kwargs):
		"""Return a page of log rows, for the list view and `frappe.get_all`."""
		query = _build_log_query(doctype, filters)
		table = query._from[0]

		fields = _select_fields(fields)
		query = query.select(*(table[f] for f in fields))

		if order_by and (ordering := _parse_order_by(table, order_by)):
			query = query.orderby(ordering[0], order=ordering[1])

		query = query.limit(frappe.utils.cint(page_length) or 20).offset(frappe.utils.cint(start))

		sql, params = query.walk()
		return get_log_db().sql(sql, params, as_dict=True)

	@staticmethod
	def get_count(doctype: str, filters=None, **kwargs) -> int:
		"""Return the total number of matching log rows, for the list view counter."""
		from frappe.query_builder.functions import Count

		query = _build_log_query(doctype, filters).select(Count("*"))
		sql, params = query.walk()
		result = get_log_db().sql(sql, params)

		return frappe.utils.cint(result[0][0]) if result else 0

	@staticmethod
	def get_stats(**kwargs):
		"""Return sidebar stats -- always empty.

		`frappe.desk.reportview.get_sidebar_stats` calls this with only `stats` and
		`filters`; it never passes the doctype. A shared base class therefore has no way to
		know which table to aggregate, so there is nothing meaningful to return. Frappe's own
		virtual DocTypes (e.g. RQ Job) return an empty dict here for the same reason.
		"""
		return {}


def _build_log_query(doctype: str, filters=None):
	"""Start a SELECT against `doctype`'s log table, with `filters` applied.

	Built with the SQLite dialect explicitly rather than through `frappe.qb`, which is bound
	to the site's primary backend. The query is only rendered here -- `walk()` returns SQL and
	parameters, which the caller runs on the log connection -- so no global is touched.
	"""
	from frappe.database.operator_map import OPERATOR_MAP
	from frappe.query_builder.utils import get_query_builder
	from frappe.types.filter import Filters

	qb = get_query_builder("sqlite")
	table = qb.DocType(doctype)
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

	# Strip any `tabX`. prefix and backticks the list view adds; drop anything that isn't a
	# bare column, since expressions and joins are out of scope for log tables.
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
