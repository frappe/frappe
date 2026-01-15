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

		commit_datetime: DF.Datetime
		function_name: DF.Data
		function_path: DF.Data
		line_number: DF.Int
		source_app: DF.Data
	# end: auto-generated types

	pass


def insert_record(source_app, function_path, function_name, line_number):
	explicit_commit = frappe.new_doc(
		"Explicit Commit",
		commit_datetime=now_datetime(),
		source_app=source_app,
		function_path=function_path,
		function_name=function_name,
		line_number=line_number,
	)
	frappe.enqueue(explicit_commit.insert, enqueue_after_commit=True)
