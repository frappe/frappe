# Copyright (c) 2023, Frappe Technologies and contributors
# For license information, please see license.txt

import json
import re
from collections import Counter

import sqlparse

import frappe
from frappe import _
from frappe.database.database import is_query_type
from frappe.model.document import Document

RECORDER_INTERCEPT_FLAG = "recorder-intercept"
RECORDER_REQUEST_SPARSE_HASH = "recorder-requests-sparse"
RECORDER_REQUEST_HASH = "recorder-requests"
TRACEBACK_PATH_PATTERN = re.compile(".*/apps/")


class RecorderRequest(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.recorder_query.recorder_query import RecorderQuery
		from frappe.types import DF

		cmd: DF.Data | None
		duration: DF.Float
		form_dict: DF.Code | None
		method: DF.Data | None
		number_of_queries: DF.Int
		path: DF.Data | None
		request_headers: DF.Code | None
		sql_queries: DF.Table[RecorderQuery]
		time: DF.Datetime | None
		time_in_queries: DF.Float
	# end: auto-generated types

	def db_insert(self, *args, **kwargs):
		pass

	def load_from_db(self):
		request_data = get(self.name)
		super(Document, self).__init__(serialize_request(request_data))

	def db_update(self):
		pass

	@staticmethod
	def get_list(args):
		requests = [serialize_request(request) for request in get()]
		return requests

	@staticmethod
	def get_count(args):
		pass

	@staticmethod
	def get_stats(args):
		pass

	@staticmethod
	def delete(args):
		pass


def administrator_only(function):
	def wrapper(*args, **kwargs):
		if frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator is allowed to use Recorder"))
		return function(*args, **kwargs)

	return wrapper


def do_not_record(function):
	def wrapper(*args, **kwargs):
		if hasattr(frappe.local, "_recorder"):
			del frappe.local._recorder
			frappe.db.sql = frappe.db._sql
		return function(*args, **kwargs)

	return wrapper


@administrator_only
def get(uuid=None, *args, **kwargs):
	if uuid:
		result = frappe.cache.hget(RECORDER_REQUEST_HASH, uuid)
	else:
		result = list(frappe.cache.hgetall(RECORDER_REQUEST_SPARSE_HASH).values())
	return result


def serialize_request(request):
	return frappe._dict(
		name=request.get("uuid"),
		path=request.get("path"),
		method=request.get("method"),
		cmd=request.get("cmd"),
		number_of_queries=request.get("queries"),
		time_in_queries=request.get("time_queries"),
		time=request.get("time"),
		duration=request.get("duration"),
		request_headers=json.dumps(request.get("headers"), indent=4),
		form_dict=json.dumps(request.get("form_dict"), indent=2),
		sql_queries=request.get("calls"),
	)


@frappe.whitelist()
@do_not_record
@administrator_only
def start(*args, **kwargs):
	frappe.cache.set_value(RECORDER_INTERCEPT_FLAG, 1, expires_in_sec=60 * 60)


@frappe.whitelist()
@do_not_record
@administrator_only
def stop(*args, **kwargs):
	frappe.cache.delete_value(RECORDER_INTERCEPT_FLAG)
	frappe.enqueue(post_process)


@frappe.whitelist()
@do_not_record
@administrator_only
def delete_requests(*args, **kwargs):
	frappe.cache.delete_value(RECORDER_REQUEST_SPARSE_HASH)
	frappe.cache.delete_value(RECORDER_REQUEST_HASH)


@frappe.whitelist()
@do_not_record
@administrator_only
def get_status(*args, **kwargs):
	return bool(frappe.cache.get_value(RECORDER_INTERCEPT_FLAG))


def post_process():
	"""post process all recorded values.

	Any processing that can be done later should be done here to avoid overhead while
	profiling. As of now following values are post-processed:
	        - `EXPLAIN` output of queries.
	        - SQLParse reformatting of queries
	        - Mark duplicates
	"""
	frappe.db.rollback()
	frappe.db.begin(read_only=True)  # Explicitly start read only transaction

	result = list(frappe.cache.hgetall(RECORDER_REQUEST_HASH).values())

	for request in result:
		for call in request["calls"]:
			formatted_query = sqlparse.format(call["query"].strip(), keyword_case="upper", reindent=True)
			call["query"] = formatted_query

			# Collect EXPLAIN for executed query
			if is_query_type(formatted_query, ("select", "update", "delete")):
				# Only SELECT/UPDATE/DELETE queries can be "EXPLAIN"ed
				try:
					call["explain_result"] = frappe.db.sql(f"EXPLAIN {formatted_query}", as_dict=True)
				except Exception:
					pass
		mark_duplicates(request)
		frappe.cache.hset(RECORDER_REQUEST_HASH, request["uuid"], request)


def mark_duplicates(request):
	exact_duplicates = Counter([call["query"] for call in request["calls"]])

	for sql_call in request["calls"]:
		sql_call["normalized_query"] = normalize_query(sql_call["query"])

	normalized_duplicates = Counter([call["normalized_query"] for call in request["calls"]])

	for index, call in enumerate(request["calls"]):
		call["index"] = index
		call["exact_copies"] = exact_duplicates[call["query"]]
		call["normalized_copies"] = normalized_duplicates[call["normalized_query"]]


def normalize_query(query: str) -> str:
	"""Attempt to normalize query by removing variables.
	This gives a different view of similar duplicate queries.

	Example:
	        These two are distinct queries:
	                `select * from user where name = 'x'`
	                `select * from user where name = 'z'`

	        But their "normalized" form would be same:
	                `select * from user where name = ?`
	"""

	try:
		q = sqlparse.parse(query)[0]
		for token in q.flatten():
			if "Token.Literal" in str(token.ttype):
				token.value = "?"
		return str(q)
	except Exception as e:
		print("Failed to normalize query ", e)

	return query
