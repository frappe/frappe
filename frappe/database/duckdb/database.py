import frappe
from frappe import qb
from frappe.database.database import Database
from frappe.database.duckdb.schema import DuckDBTable


def get_type_map():
	return {
		"Currency": ("decimal", "21,9"),
		"Int": ("int", "11"),
		"Long Int": ("bigint", "20"),
		"Float": ("decimal", "21,9"),
		"Percent": ("decimal", "21,9"),
		"Check": ("tinyint", ""),
		"Small Text": ("text", ""),
		"Long Text": ("longtext", ""),
		"Code": ("longtext", ""),
		"Text Editor": ("longtext", ""),
		"Markdown Editor": ("longtext", ""),
		"HTML Editor": ("longtext", ""),
		"Date": ("date", ""),
		"Datetime": ("datetime", "6"),
		"Time": ("time", "6"),
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
		"Signature": ("longtext", ""),
		"Color": ("varchar", frappe.db.VARCHAR_LEN),
		"Barcode": ("longtext", ""),
		"Geolocation": ("longtext", ""),
		"Duration": ("decimal", "21,9"),
		"Icon": ("varchar", frappe.db.VARCHAR_LEN),
		"Phone": ("varchar", frappe.db.VARCHAR_LEN),
		"Autocomplete": ("varchar", frappe.db.VARCHAR_LEN),
		"JSON": ("json", ""),
	}


def sync_to_duckdb():
	res = frappe.get_all("DocType", {"sync_to_duckdb": 1}, pluck="name")
	for dt in res:
		_dt = qb.DocType(dt)

		res = qb.from_(_dt).select(_dt.star).run(as_list=True)


def drop_all_tables():
	res = frappe.duckdb.sql("show tables").fetchall()
	for x in res:
		frappe.duckdb.sql(f'drop table "{x[0]}";')
