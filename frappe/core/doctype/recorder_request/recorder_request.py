# Copyright (c) 2023, Frappe Technologies and contributors
# For license information, please see license.txt

import json
import re

import frappe
from frappe.model.document import Document
from frappe.recorder import get
from frappe.utils import cint, compare, make_filter_dict


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
		method: DF.Literal["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
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
		request = serialize_request(request_data)
		super(Document, self).__init__(request)

	def db_update(self):
		pass

	@staticmethod
	def get_list(args):
		start = cint(args.get("start")) or 0
		page_length = cint(args.get("page_length")) or 20
		requests = RecorderRequest.get_filtered_requests(args)[start : start + page_length]
		if args.get("order_by"):
			sort_key, sort_order = args.get("order_by").split(".")[1].split(" ")
			sort_key = sort_key.replace("`", "")
			return sorted(requests, key=lambda r: r[sort_key], reverse=bool(sort_order == "desc"))
		return sorted(requests, key=lambda r: r.duration, reverse=1)

	@staticmethod
	def get_count(args):
		return len(RecorderRequest.get_filtered_requests(args))

	@staticmethod
	def get_stats(args):
		pass

	@staticmethod
	def delete(self):
		pass

	@staticmethod
	def get_filtered_requests(args):
		filters = make_filter_dict(args.get("filters"))
		requests = [serialize_request(request) for request in get()]
		filtered_requests = []
		for request in requests:
			filter_flag = 1
			for field in filters:
				operator = "in" if filters[field][0] == "like" else filters[field][0]
				if not compare(request[field], operator, filters[field][1]):
					filter_flag = 0
			if filter_flag:
				filtered_requests.append(request)
		return filtered_requests


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
		request_headers=frappe.as_json(request.get("headers"), indent=4),
		form_dict=frappe.as_json(request.get("form_dict"), indent=4),
		sql_queries=request.get("calls"),
	)

	return request
