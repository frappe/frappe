# Copyright (c) 2023, Frappe Technologies and contributors
# For license information, please see license.txt

import json
from collections import Counter, defaultdict

import frappe
from frappe import _
from frappe.core.doctype.recorder.db_optimizer import DBOptimizer, DBTable
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.model.document import Document
from frappe.recorder import RECORDER_REQUEST_HASH
from frappe.recorder import get as get_recorder_data
from frappe.utils import cint, cstr, evaluate_filters, get_table_name
from frappe.utils.caching import redis_cache


class Recorder(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.recorder_query.recorder_query import RecorderQuery
		from frappe.core.doctype.recorder_suggested_index.recorder_suggested_index import (
			RecorderSuggestedIndex,
		)
		from frappe.types import DF

		cmd: DF.Data | None
		duration: DF.Float
		event_type: DF.Data | None
		form_dict: DF.Code | None
		method: DF.Literal["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
		number_of_queries: DF.Int
		path: DF.Data | None
		profile: DF.Code | None
		request_headers: DF.Code | None
		sql_queries: DF.Table[RecorderQuery]
		suggested_indexes: DF.Table[RecorderSuggestedIndex]
		time: DF.Datetime | None
		time_in_queries: DF.Float
	# end: auto-generated types

	def load_from_db(self):
		request_data = get_recorder_data(self.name)
		if not request_data:
			raise frappe.DoesNotExistError
		request = serialize_request(request_data)
		super(Document, self).__init__(request)

	@staticmethod
	def get_list(filters=None, start=0, page_length=20, order_by="duration desc"):
		requests = Recorder.get_filtered_requests(filters)[start : start + page_length]

		if order_by_statment := order_by:
			order_by_statment = order_by_statment.split(",")[0]
			if "." in order_by_statment:
				order_by_statment = order_by_statment.split(".")[1]

			if " " in order_by_statment:
				sort_key, sort_order = order_by_statment.split(" ", 1)
			else:
				sort_key = order_by_statment
				sort_order = "desc"

			sort_key = sort_key.replace("`", "")
			return sorted(requests, key=lambda r: r.get(sort_key) or 0, reverse=bool(sort_order == "desc"))

		return sorted(requests, key=lambda r: r.duration, reverse=1)

	@staticmethod
	def get_count(filters=None):
		return len(Recorder.get_filtered_requests(filters))

	@staticmethod
	def get_filtered_requests(filters):
		requests = [serialize_request(request) for request in get_recorder_data()]
		return [req for req in requests if evaluate_filters(req, filters)]

	@staticmethod
	def get_stats(args):
		pass

	@staticmethod
	def delete(self):
		pass

	def db_insert(self, *args, **kwargs):
		pass

	def db_update(self):
		pass


def serialize_request(request):
	request = frappe._dict(request)
	if request.get("calls"):
		for i in request.calls:
			i["stack"] = frappe.as_json(i["stack"])
			i["explain_result"] = frappe.as_json(i["explain_result"])
	request.update(
		name=request.get("uuid"),
		number_of_queries=request.get("queries"),
		time_in_queries=request.get("time_queries"),
		request_headers=frappe.as_json(request.get("headers", {}), indent=4),
		form_dict=frappe.as_json(request.get("form_dict", {}), indent=4),
		sql_queries=request.get("calls"),
		suggested_indexes=request.get("suggested_indexes"),
		modified=request.get("time"),
		creation=request.get("time"),
	)

	return request


@frappe.whitelist()
def add_indexes(indexes):
	frappe.only_for("Administrator")
	indexes = json.loads(indexes)

	for index in indexes:
		frappe.enqueue(_add_index, table=index["table"], column=index["column"])
	frappe.msgprint(_("Enqueued creation of indexes"), alert=True)


def _add_index(table, column):
	doctype = get_doctype_name(table)
	frappe.db.add_index(doctype, [column])
	frappe.msgprint(
		_("Index created successfully on column {0} of doctype {1}").format(column, doctype),
		alert=True,
		realtime=True,
	)


@frappe.whitelist()
def optimize(recorder_id: str):
	frappe.only_for("Administrator")
	frappe.enqueue(_optimize, recorder_id=recorder_id, queue="long")


def _optimize(recorder_id):
	record: Recorder = frappe.get_doc("Recorder", recorder_id)
	total_duration = record.time_in_queries

	# Any index with query time less than 5% of total time is not suggested
	PERCENT_DURATION_THRESHOLD_OVERALL = 0.05
	# Any query with duration less than 0.5% of total duration is not analyzed
	PERCENT_DURATION_THRESHOLD_QUERY = 0.005

	# Index suggestion -> Query duration
	index_suggestions = Counter()
	for idx, captured_query in enumerate(record.sql_queries, start=1):
		query = cstr(captured_query.query)
		frappe.publish_progress(
			idx / len(record.sql_queries) * 100,
			title="Analyzing Queries",
			doctype=record.doctype,
			docname=record.name,
			description=f"Analyzing query: {query[:140]}",
		)
		if captured_query.duration < total_duration * PERCENT_DURATION_THRESHOLD_QUERY:
			continue
		if not query.lower().strip().startswith(("select", "update", "delete")):
			continue
		if index := _optimize_query(query):
			index_suggestions[(index.table, index.column)] += captured_query.duration

	suggested_indexes = index_suggestions.most_common(3)
	suggested_indexes = [
		idx for idx in suggested_indexes if idx[1] > total_duration * PERCENT_DURATION_THRESHOLD_OVERALL
	]

	if not suggested_indexes:
		frappe.msgprint(
			_("No automatic optimization suggestions available."),
			title=_("No Suggestions"),
			realtime=True,
		)
		return

	data = frappe.cache.hget(RECORDER_REQUEST_HASH, record.name)
	data["suggested_indexes"] = [{"table": idx[0][0], "column": idx[0][1]} for idx in suggested_indexes]
	frappe.cache.hset(RECORDER_REQUEST_HASH, record.name, data)
	frappe.publish_realtime("recorder-analysis-complete", user=frappe.session.user)
	frappe.msgprint(_("Query analysis complete. Check suggested indexes."), realtime=True, alert=True)


def _optimize_query(query):
	optimizer = DBOptimizer(query=query)
	tables = optimizer.tables_examined()

	# Note: Two passes are required here because we first need basic data to understand which
	# columns need to be analyzed to get accurate cardinality.
	for table in tables:
		doctype = get_doctype_name(table)
		stats = _fetch_table_stats(doctype, columns=[])
		if not stats:
			return
		db_table = DBTable.from_frappe_ouput(stats)
		optimizer.update_table_data(db_table)

	potential_indexes = optimizer.potential_indexes()
	tablewise_columns = defaultdict(list)
	for idx in potential_indexes:
		tablewise_columns[idx.table].append(idx.column)

	for table in tables:
		doctype = get_doctype_name(table)
		stats = _fetch_table_stats(doctype, columns=tablewise_columns[table])
		if not stats:
			return
		db_table = DBTable.from_frappe_ouput(stats)
		optimizer.update_table_data(db_table)

	return optimizer.suggest_index()


def _fetch_table_stats(doctype: str, columns: list[str]) -> dict | None:
	def sql_bool(val):
		return cstr(val).lower() in ("yes", "1", "true")

	if not frappe.db.table_exists(doctype):
		return

	table = get_table_name(doctype, wrap_in_backticks=True)

	schema = []
	for field in frappe.db.sql(f"describe {table}", as_dict=True):
		schema.append(
			{
				"column": field["Field"],
				"type": field["Type"],
				"is_nullable": sql_bool(field["Null"]),
				"default": field["Default"],
			}
		)

	def update_cardinality(column, value):
		for col in schema:
			if col["column"] == column:
				col["cardinality"] = value
				break

	indexes = []
	for idx in frappe.db.sql(f"show index from {table}", as_dict=True):
		indexes.append(
			{
				"unique": not sql_bool(idx["Non_unique"]),
				"cardinality": idx["Cardinality"],
				"name": idx["Key_name"],
				"sequence": idx["Seq_in_index"],
				"nullable": sql_bool(idx["Null"]),
				"column": idx["Column_name"],
				"type": idx["Index_type"],
			}
		)
		if idx["Seq_in_index"] == 1:
			update_cardinality(idx["Column_name"], idx["Cardinality"])

	total_rows = cint(
		frappe.db.sql(
			f"""select table_rows
			   from  information_schema.tables
			   where table_name = 'tab{doctype}'"""
		)[0][0]
	)

	# fetch accurate cardinality for columns by query. WARN: This can take A LOT of time.
	for column in columns:
		cardinality = _get_column_cardinality(table, column)
		update_cardinality(column, cardinality)

	return {
		"table_name": table.strip("`"),
		"total_rows": total_rows,
		"schema": schema,
		"indexes": indexes,
	}


@redis_cache
def _get_column_cardinality(table, column):
	return frappe.db.sql(f"select count(distinct {column}) from {table}")[0][0]


def get_doctype_name(table_name: str) -> str:
	return table_name.removeprefix("tab")
