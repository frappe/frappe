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


@frappe.whitelist()
def sync_to_duckdb():
	# TODO: permissions
	from frappe.database.schema import DBTable

	# create non-existent tables
	doctypes = frappe.db.get_all("DuckDB Sync Item", fields=["doc_type"], pluck="doc_type")
	table_names = set()
	for x in doctypes:
		table_names.add(DBTable(x).table_name)
	print("Table names:", table_names)
	print("DuckDB:", frappe.duckdb)
	res = frappe.duckdb.sql("show tables").fetchall()
	res = set([x[0] for x in res])
	to_create = table_names - res
	print(to_create)


@frappe.whitelist()
def drop_all_tables():
	# TODO: permissions
	res = frappe.duckdb.sql("show tables").fetchall()
	for x in res:
		frappe.duckdb.sql(f'drop table "{x[0]}";')
