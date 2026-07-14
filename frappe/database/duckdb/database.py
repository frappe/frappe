import frappe
from frappe import qb
from frappe.database import get_duckdb
from frappe.database.database import Database
from frappe.database.duckdb.schema import DuckDBTable


def get_type_map():
	return {
		"Currency": ("decimal", "21,9"),
		"Int": ("int", ""),
		"Long Int": ("bigint", "20"),
		"Float": ("decimal", "21,9"),
		"Percent": ("decimal", "21,9"),
		"Check": ("tinyint", ""),
		"Small Text": ("text", ""),
		"Long Text": ("text", ""),
		"Code": ("text", ""),
		"Text Editor": ("text", ""),
		"Markdown Editor": ("text", ""),
		"HTML Editor": ("text", ""),
		"Date": ("date", ""),
		"Datetime": ("datetime", ""),
		"Time": ("time", ""),
		"Text": ("text", ""),
		"Data": ("varchar", frappe.db.VARCHAR_LEN),
		"Link": ("varchar", frappe.db.VARCHAR_LEN),
		"Dynamic Link": ("varchar", frappe.db.VARCHAR_LEN),
		"Password": ("text", ""),
		"Select": ("varchar", frappe.db.VARCHAR_LEN),
		"Rating": ("decimal", "3,2"),
		"Read Only": ("varchar", frappe.db.VARCHAR_LEN),
		"Attach": ("text", ""),
		"Attach Image": ("text", ""),
		"Signature": ("text", ""),
		"Color": ("varchar", frappe.db.VARCHAR_LEN),
		"Barcode": ("text", ""),
		"Geolocation": ("text", ""),
		"Duration": ("decimal", "21,9"),
		"Icon": ("varchar", frappe.db.VARCHAR_LEN),
		"Phone": ("varchar", frappe.db.VARCHAR_LEN),
		"Autocomplete": ("varchar", frappe.db.VARCHAR_LEN),
		"JSON": ("json", ""),
	}


def get_latest_sync(doctype: str | None = None):
	if doctype:
		if latest_sync := frappe.db.get_all(
			"DuckDB Sync", filters={"doc_type": doctype}, pluck="name", order_by="creation desc", limit=1
		):
			return frappe.get_doc("DuckDB Sync", latest_sync[0]).get_duckdb_conn()
	return None


class DuckDBConnection:
	"""Wraps a DuckDB connection so fetch results automatically convert Decimal to float."""

	def __init__(self, conn):
		self._conn = conn

	def __getattr__(self, name):
		return getattr(self._conn, name)

	def execute(self, query, parameters=None):
		rel = self._conn.execute(query, parameters) if parameters is not None else self._conn.execute(query)
		return DuckDBRelation(rel)

	def sql(self, query):
		return DuckDBRelation(self._conn.sql(query))


class DuckDBRelation:
	"""Wraps a DuckDB relation to convert Decimal results to float on fetch."""

	def __init__(self, rel):
		self._rel = rel

	def __getattr__(self, name):
		return getattr(self._rel, name)

	def fetchall(self):
		from decimal import Decimal

		return [tuple(float(v) if isinstance(v, Decimal) else v for v in row) for row in self._rel.fetchall()]

	def fetchone(self):
		from decimal import Decimal

		row = self._rel.fetchone()
		if row is None:
			return None
		return tuple(float(v) if isinstance(v, Decimal) else v for v in row)

	def fetchmany(self, size=1):
		from decimal import Decimal

		return [
			tuple(float(v) if isinstance(v, Decimal) else v for v in row) for row in self._rel.fetchmany(size)
		]


def start_duckdb_sync():
	_dt = qb.DocType("Doctype To Sync")
	to_sync = (
		qb.from_(_dt)
		.select(_dt.doc_type)
		.distinct()
		.where(_dt.parenttype.eq("Report") & _dt.parentfield.eq("doctype_to_sync"))
		.run(pluck="doc_type")
	)
	for x in to_sync:
		doc = frappe.get_doc(
			{
				"doctype": "DuckDB Sync",
				"doc_type": x,
			}
		).insert()
		doc.submit()
