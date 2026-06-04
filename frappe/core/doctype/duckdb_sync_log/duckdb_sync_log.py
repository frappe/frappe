# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import qb
from frappe.database.duckdb.database import get_duckdb
from frappe.database.duckdb.schema import DuckDBTable
from frappe.model.document import Document


class DuckDBSyncLog(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.duckdb_sync_log_item.duckdb_sync_log_item import DuckDBSyncLogItem
		from frappe.types import DF

		amended_from: DF.Link | None
		db_tables: DF.Table[DuckDBSyncLogItem]
		doc_type: DF.Link | None
		filename: DF.Data | None
	# end: auto-generated types

	_DOCTYPE_NAME = "DuckDB Sync Log"

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
		self.sync()

	def get_duckdb_conn(self):
		return get_duckdb(False, frappe.conf.db_name, self.filename)

	def sync(self):
		duck_conn = self.get_duckdb_conn()
		# create non-existent tables
		existing = set([x[0] for x in duck_conn.sql("show tables").fetchall()])

		for x in self.db_tables:
			ddbt = DuckDBTable(x.table)
			if ddbt.table_name not in existing:
				ddbt.sync(duck_conn)
		duck_conn.close()
		# frappe.enqueue(
		# 	method="frappe.database.duckdb.database.sync_data",
		# 	timeout="300",
		# 	is_async=True,
		# 	enqueue_after_commit=True,
		# )
		# frappe.toast("Data sync started")
