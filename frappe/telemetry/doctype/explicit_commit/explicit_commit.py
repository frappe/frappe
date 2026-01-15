# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class ExplicitCommit(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		count: DF.Int
		function_name: DF.Data
		function_path: DF.Data
		source_app: DF.Data
	# end: auto-generated types

	pass


def insert_record(source_app, function_path, function_name):
	if doc_name := frappe.get_all(
		"Explicit Commit",
		{
			"source_app": source_app,
			"function_path": function_path,
			"function_name": function_name,
		},
		["name", "count"],
		limit=1,
	):
		frappe.set_value("Explicit Commit", doc_name[0].name, "count", doc_name[0].count + 1)
	else:
		frappe.new_doc(
			"Explicit Commit",
			source_app=source_app,
			function_path=function_path,
			function_name=function_name,
		).insert(ignore_permissions=True)
