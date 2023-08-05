# Copyright (c) 2023, Frappe Technologies and contributors
# For license information, please see license.txt

import json
import re

import frappe
from frappe.model.document import Document
from frappe.recorder import get


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
		request = serialize_request(request_data)
		super(Document, self).__init__(request)

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
