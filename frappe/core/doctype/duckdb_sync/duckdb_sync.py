# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import qb
from frappe.database.duckdb.database import get_duckdb
from frappe.database.duckdb.schema import DuckDBTable
from frappe.model.document import Document


class DuckDBSync(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.duckdb_sync_item.duckdb_sync_item import DuckDBSyncItem
		from frappe.types import DF

		amended_from: DF.Link | None
		db_tables: DF.Table[DuckDBSyncItem]
		doc_type: DF.Link | None
		filename: DF.Data | None
	# end: auto-generated types

	_DOCTYPE_NAME = "DuckDB Sync"

	def before_save(self):
		filename = self.doc_type.lower().replace(" ", "_")
		self.filename = f"{frappe.conf.db_name}_{filename}.duckdb"

		self.append("db_tables", {"table": self.doc_type})
		df = qb.DocType("DocField")
		if (
			res := qb.from_(df)
			.select(df.options)
			.where(df.parent.eq(self.doc_type) & df.fieldtype.eq("Table"))
			.run()
		):
			for tb in res:
				self.append("db_tables", {"table": tb[0]})

	def on_submit(self):
		self.sync_schema()
		start_data_sync(self.name)

	def get_duckdb_conn(self):
		return get_duckdb(False, frappe.conf.db_name, self.filename)

	def sync_schema(self):
		duck_conn = self.get_duckdb_conn()
		existing = set([x[0] for x in duck_conn.sql("show tables").fetchall()])

		for x in self.db_tables:
			ddbt = DuckDBTable(x.table)
			if ddbt.table_name not in existing:
				ddbt.sync(duck_conn)
		duck_conn.close()


@frappe.whitelist()
def start_data_sync(docname: str):
	# TODO: permissions
	frappe.enqueue(
		method="frappe.core.doctype.duckdb_sync.duckdb_sync.sync_data_to_duckdb",
		queue="long",
		is_async=True,
		enqueue_after_commit=True,
		docname=docname,
	)


def sync_data_to_duckdb(docname: str):
	# TODO: permissions
	sync_dt = qb.DocType("DuckDB Sync Item")
	if (
		unsynced := qb.from_(sync_dt)
		.select(sync_dt.name, sync_dt.table)
		.where(sync_dt.parent.eq(docname) & sync_dt.synced.eq(False))
		.orderby(sync_dt.idx)
		.limit(1)
		.for_update(skip_locked=True)
		.run(as_dict=True)
	):
		dt = unsynced[0]["table"]
		name = unsynced[0]["name"]
		duck_tb = DuckDBTable(dt)

		# connect to mariadb
		doc = frappe.get_doc("DuckDB Sync", docname)
		conn = doc.get_duckdb_conn()
		conn.sql(
			f"attach 'user={frappe.conf.db_name} password={frappe.conf.db_password} host={frappe.conf.db_host} database={frappe.conf.db_name}' as mariadb_db (TYPE mysql);"
		)
		columns = frappe.get_meta(dt).get_valid_columns()
		# quotted fields
		columns_sql = ", ".join([f'"{x}"' for x in columns])
		query = f'insert into "{duck_tb.table_name}" ({columns_sql}) select {columns_sql} from mariadb_db."{duck_tb.table_name}";'
		conn.sql(query)
		conn.close()

		# update flag
		frappe.db.set_value("DuckDB Sync Item", name, "synced", True)

		# schedule next
		frappe.enqueue(
			method="frappe.core.doctype.duckdb_sync.duckdb_sync.sync_data_to_duckdb",
			queue="long",
			is_async=True,
			enqueue_after_commit=True,
			docname=docname,
		)
