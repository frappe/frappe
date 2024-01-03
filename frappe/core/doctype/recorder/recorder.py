# Copyright (c) 2023, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.recorder import get as get_recorder_data
from frappe.utils import cint, evaluate_filters, make_filter_dict


class Recorder(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.recorder_query.recorder_query import RecorderQuery
		from frappe.types import DF

		cmd: DF.Data | None
		duration: DF.Float
		event_type: DF.Data | None
		form_dict: DF.Code | None
		method: DF.Literal["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
		number_of_queries: DF.Int
		path: DF.Data | None
		request_headers: DF.Code | None
		sql_queries: DF.Table[RecorderQuery]
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
	def get_list(args):
		start = cint(args.get("start")) or 0
		page_length = cint(args.get("page_length")) or 20
		requests = Recorder.get_filtered_requests(args)[start : start + page_length]

		if order_by_statment := args.get("order_by"):
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
	def get_count(args):
		return len(Recorder.get_filtered_requests(args))

	@staticmethod
	def get_filtered_requests(args):
		filters = args.get("filters")
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
		request_headers=frappe.as_json(request.get("headers"), indent=4),
		form_dict=frappe.as_json(request.get("form_dict"), indent=4),
		sql_queries=request.get("calls"),
		modified=request.get("time"),
		creation=request.get("time"),
	)

	return request
