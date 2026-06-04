# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import qb
from frappe.model.document import Document


class DuckDBSyncLog(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.duckdb_sync_log_item.duckdb_sync_log_item import DuckDBSyncLogItem
		from frappe.types import DF

		db_tables: DF.Table[DuckDBSyncLogItem]
		doc_type: DF.Link | None
	# end: auto-generated types

	_DOCTYPE_NAME = "DuckDB Sync Log"

	def before_save(self):
		self.append("db_tables", {"table": f"tab{self.doc_type}"})
		df = qb.DocType("DocField")
		if (
			res := qb.from_(df)
			.select(df.options)
			.where(df.parent.eq(self.doc_type) & df.fieldtype.eq("Table"))
			.run()
		):
			for tb in res:
				self.append("db_tables", {"table": f"tab{tb[0]}"})
