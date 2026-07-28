# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

from datetime import time, timedelta

import pyarrow as pa

import frappe
from frappe import qb
from frappe.database import get_duckdb
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
		doc_type: DF.Link
		filename: DF.Data | None
	# end: auto-generated types

	_DOCTYPE_NAME = "DuckDB Sync"

	def before_save(self):
		dt = self.doc_type.lower().replace(" ", "_")
		self.filename = f"{dt}_{self.name}.duckdb"

		self.db_tables = []
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
		return get_duckdb(False, self.filename)

	def sync_schema(self):
		duck_conn = self.get_duckdb_conn()
		existing = set([x[0] for x in duck_conn.sql("show tables").fetchall()])

		for x in self.db_tables:
			ddbt = DuckDBTable(x.table)
			if ddbt.table_name not in existing:
				ddbt.sync(duck_conn)
		duck_conn.close()

	def on_cancel(self):
		self.flags.ignore_links = True

	def on_trash(self):
		if self.docstatus.is_cancelled():
			from frappe.database import delete_duckdb_file

			delete_duckdb_file(self.filename)


@frappe.whitelist()
def is_data_sync_pending(docname: str):
	frappe.has_permission("DuckDB Sync", ptype="write", throw=True)
	return frappe.db.exists("DuckDB Sync Item", {"parent": docname, "synced": False})


@frappe.whitelist()
def start_data_sync(docname: str):
	frappe.has_permission("DuckDB Sync", ptype="write", throw=True)
	timeout = frappe.db.get_single_value("System Settings", "sync_timeout") or 25 * 60
	frappe.enqueue(
		method="frappe.core.doctype.duckdb_sync.duckdb_sync.sync_data_to_duckdb",
		queue="long",
		timeout=timeout,
		enqueue_after_commit=True,
		docname=docname,
	)


def cleanup_old_syncs():
	cutoff = frappe.utils.add_days(frappe.utils.now_datetime(), -7)
	old_syncs = frappe.get_all(
		"DuckDB Sync",
		filters={"creation": ["<", cutoff], "docstatus": 1},
	)
	for sync in old_syncs:
		try:
			doc = frappe.get_doc("DuckDB Sync", sync.name)
			doc.cancel()
			doc.delete()
			frappe.db.commit()
		except Exception:
			frappe.log_error("DuckDB cleanup failed", frappe.get_traceback())
			frappe.db.rollback()


def sync_data_to_duckdb(docname: str):
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

		timeout = frappe.db.get_single_value("System Settings", "sync_timeout") or 25 * 60
		conn = frappe.get_doc("DuckDB Sync", docname).get_duckdb_conn()

		conn.execute(f'delete from "{duck_tb.table_name}";').fetchall()

		_dt = qb.DocType(dt)
		columns = frappe.get_meta(dt).get_valid_columns()
		query = qb.from_(_dt)
		for col in columns:
			query = query.select(_dt[col])
		schema = duck_tb.get_arrow_schema()

		with frappe.db.unbuffered_cursor():
			iter = query.run(as_dict=True, as_iterator=True)
			field_list = ", ".join(f'"{c}"' for c in schema.names)
			time_columns = [
				name
				for name, dtype in zip(schema.names, schema.types, strict=False)
				if pa.types.is_time(dtype)
			]

			def timedelta_to_time(td):
				total_seconds = int(td.total_seconds()) % 86400
				hours, remainder = divmod(total_seconds, 3600)
				minutes, seconds = divmod(remainder, 60)
				return time(hours, minutes, seconds, td.microseconds)

			# an iterator to create RecordBatch from list
			def recordbatch_from_list(iter, schema):
				batch_size = 204800
				rows = []
				for row in iter:
					for col in time_columns:
						if isinstance(row.get(col), timedelta):
							row[col] = timedelta_to_time(row[col])
					rows.append(row)
					if len(rows) >= batch_size:
						batch = pa.RecordBatch.from_pylist(rows, schema=schema)
						yield batch
						rows = []
						del batch

				if rows:
					batch = pa.RecordBatch.from_pylist(rows, schema=schema)
					yield batch
					rows = []
					del batch

			# streaming RecordBatch on demand
			# sets backpressure on sql cursor through 'recordbatch_from_list' iterator
			reader = pa.RecordBatchReader.from_batches(schema, recordbatch_from_list(iter, schema))

			for batch in reader:
				# zero-copy streaming: duckdb understands arrow table's memory layout
				arrow_table = pa.Table.from_batches([batch])
				conn.register("arrow_table", arrow_table)
				conn.execute(
					f'insert into "{duck_tb.table_name}" ({field_list}) select {field_list} from arrow_table;'
				).fetchall()
				conn.unregister("arrow_table")
				del arrow_table

		conn.close()
		# update flag
		frappe.db.set_value("DuckDB Sync Item", name, "synced", True)

		# schedule next
		frappe.enqueue(
			method="frappe.core.doctype.duckdb_sync.duckdb_sync.sync_data_to_duckdb",
			queue="long",
			timeout=timeout,
			is_async=True,
			enqueue_after_commit=True,
			docname=docname,
		)
