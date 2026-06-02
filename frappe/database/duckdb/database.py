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


@frappe.whitelist()
def sync_to_duckdb():
	# TODO: permissions
	frappe.duckdb = get_duckdb(read_only=False)
	# create non-existent tables
	existing = frappe.duckdb.sql("show tables").fetchall()
	existing = set([x[0] for x in existing])

	doctypes = frappe.db.get_all("DuckDB Sync Item", fields=["doc_type"], pluck="doc_type")
	for x in doctypes:
		ddbt = DuckDBTable(x)
		if ddbt.table_name not in existing:
			ddbt.sync()
	frappe.duckdb.close()
	sync_data()


def sync_data():
	frappe.duckdb = get_duckdb(read_only=False)
	frappe.duckdb.sql(
		f"attach 'user={frappe.conf.db_name} password={frappe.conf.db_password} host={frappe.conf.db_host} database={frappe.conf.db_name}' as mariadb (TYPE mysql);"
	)
	doctypes = frappe.db.get_all("DuckDB Sync Item", fields=["doc_type"], pluck="doc_type")
	for x in doctypes:
		ddbt = DuckDBTable(x)
		frappe.duckdb.sql(f'insert into "{ddbt.table_name}" select * from mariadb."{ddbt.table_name}";')

	frappe.duckdb.close()


@frappe.whitelist()
def drop_tables():
	# TODO: permissions
	frappe.duckdb = get_duckdb(read_only=False)
	doctypes = frappe.db.get_all("DuckDB Sync Item", fields=["doc_type"], pluck="doc_type")
	for x in doctypes:
		frappe.duckdb.sql(f'drop table if exists"{DuckDBTable(x).table_name}";')
	frappe.duckdb.close()


@frappe.whitelist()
def drop_all_tables():
	# TODO: permissions
	frappe.duckdb = get_duckdb(read_only=False)
	res = frappe.duckdb.sql("show tables").fetchall()
	for x in res:
		frappe.duckdb.sql(f'drop table "{x[0]}";')
	frappe.duckdb.close()


@frappe.whitelist()
def open_duckdb_connection():
	# TODO: permissions
	if not frappe.duckdb:
		frappe.duckdb = get_duckdb()


@frappe.whitelist()
def close_connection():
	# TODO: permissions
	if frappe.duckdb:
		frappe.duckdb.close()
