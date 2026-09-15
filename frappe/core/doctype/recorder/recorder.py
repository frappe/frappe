# Copyright (c) 2023, Frappe Technologies and contributors
# For license information, please see license.txt

from collections import Counter, defaultdict

import frappe
from frappe import _
from frappe.core.doctype.recorder.db_optimizer import DBOptimizer, DBTable
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.model.document import Document
from frappe.recorder import RECORDER_REQUEST_HASH
from frappe.recorder import get as get_recorder_data
from frappe.utils import cstr, evaluate_filters, get_table_name
from frappe.utils.caching import redis_cache


class Recorder(Document):
	_DOCTYPE_NAME = "Recorder"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.recorder_event.recorder_event import RecorderEvent
		from frappe.core.doctype.recorder_query.recorder_query import RecorderQuery
		from frappe.core.doctype.recorder_suggested_index.recorder_suggested_index import (
			RecorderSuggestedIndex,
		)
		from frappe.types import DF

		apps_involved: DF.Data | None
		cmd: DF.Data | None
		duration: DF.Float
		event_type: DF.Data | None
		form_dict: DF.Code | None
		method: DF.Literal["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
		number_of_events: DF.Int
		number_of_queries: DF.Int
		path: DF.Data | None
		profile: DF.Code | None
		request_headers: DF.Code | None
		sql_queries: DF.Table[RecorderQuery]
		suggested_indexes: DF.Table[RecorderSuggestedIndex]
		time: DF.Datetime | None
		time_in_queries: DF.Float
		timeline: DF.Table[RecorderEvent]
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

	events = request.get("events") or []
	for event in events:
		# indent the method by its nesting depth so the grid reads as a call tree.
		# non-breaking spaces render the indentation without depending on CSS white-space.
		indent = "\u00a0\u00a0\u00a0\u00a0" * event.get("depth", 0)
		event["label"] = indent + (event.get("method") or "")
		if isinstance(event.get("apps"), list):
			event["apps"] = ", ".join(event["apps"])
		if isinstance(event.get("handlers"), list):
			event["handlers"] = "\n".join(event["handlers"])

	request.update(
		name=request.get("uuid"),
		number_of_queries=request.get("queries"),
		time_in_queries=request.get("time_queries"),
		number_of_events=request.get("number_of_events") or len(events),
		apps_involved=request.get("apps_involved"),
		request_headers=frappe.as_json(request.get("headers", {}), indent=4),
		form_dict=frappe.as_json(request.get("form_dict", {}), indent=4),
		sql_queries=request.get("calls"),
		timeline=events,
		suggested_indexes=request.get("suggested_indexes"),
		modified=request.get("time"),
		creation=request.get("time"),
	)

	return request


@frappe.whitelist()
def add_indexes(indexes: str | list[dict]):
	frappe.only_for("Administrator")
	indexes = frappe.parse_json(indexes)

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
	if not frappe.db.table_exists(doctype):
		return

	table_name = get_table_name(doctype)
	schema = [
		{
			"column": field.name,
			"type": field.type,
			"is_nullable": not field.not_nullable,
			"default": field.default,
		}
		for field in frappe.db.get_table_columns_description(table_name)
	]

	def update_cardinality(column, value):
		for col in schema:
			if col["column"] == column:
				col["cardinality"] = value
				break

	indexes = _fetch_table_indexes(table_name)
	for index in indexes:
		if index["sequence"] == 1 and index["cardinality"] is not None:
			update_cardinality(index["column"], index["cardinality"])

	# fetch accurate cardinality for columns by query. WARN: This can take A LOT of time.
	for column in columns:
		cardinality = _get_column_cardinality(table_name, column)
		update_cardinality(column, cardinality)

	return {
		"table_name": table_name,
		"total_rows": frappe.db.estimate_count(doctype),
		"schema": schema,
		"indexes": indexes,
	}


def _fetch_table_indexes(table_name: str) -> list[dict]:
	if frappe.db.db_type == "postgres":
		return _fetch_postgres_table_indexes(table_name)
	return _fetch_mariadb_table_indexes(table_name)


def _fetch_postgres_table_indexes(table_name: str) -> list[dict]:
	return frappe.db.sql(
		"""
		SELECT
			i.indisunique AS "unique",
			NULL::bigint AS cardinality,
			index_info.relname AS name,
			indexed_column.ordinality AS sequence,
			NOT column_info.attnotnull AS nullable,
			column_info.attname AS column,
			method.amname AS type
		FROM pg_index i
		JOIN pg_class table_info ON table_info.oid = i.indrelid
		JOIN pg_class index_info ON index_info.oid = i.indexrelid
		JOIN pg_namespace namespace ON namespace.oid = table_info.relnamespace
		JOIN pg_am method ON method.oid = index_info.relam
		JOIN LATERAL unnest(i.indkey) WITH ORDINALITY AS indexed_column(attnum, ordinality) ON TRUE
		JOIN pg_attribute column_info
			ON column_info.attrelid = table_info.oid AND column_info.attnum = indexed_column.attnum
		WHERE table_info.relname = %(table_name)s
			AND namespace.nspname = %(schema)s
			AND indexed_column.ordinality <= i.indnkeyatts
			AND i.indisvalid
			AND i.indisready
			AND i.indislive
			AND i.indpred IS NULL
			AND i.indexprs IS NULL
			AND method.amname = 'btree'
		ORDER BY index_info.relname, indexed_column.ordinality
		""",
		{"table_name": table_name, "schema": frappe.db.db_schema},
		as_dict=True,
	)


def _fetch_mariadb_table_indexes(table_name: str) -> list[dict]:
	return frappe.db.sql(
		"""
		SELECT
			NOT non_unique AS `unique`,
			cardinality,
			index_name AS name,
			seq_in_index AS sequence,
			nullable = 'YES' AS nullable,
			column_name AS `column`,
			index_type AS type
		FROM information_schema.statistics
		WHERE table_schema = %(schema)s AND table_name = %(table_name)s
		ORDER BY index_name, seq_in_index
		""",
		{"schema": frappe.db.cur_db_name, "table_name": table_name},
		as_dict=True,
	)


@redis_cache
def _get_column_cardinality(table, column):
	from frappe.query_builder.functions import Count

	table = frappe.qb.Table(table)
	return frappe.qb.from_(table).select(Count(table[column]).distinct()).run()[0][0]


def get_doctype_name(table_name: str) -> str:
	return table_name.removeprefix("tab")
