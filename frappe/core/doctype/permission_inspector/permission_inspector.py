# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.permissions import _pop_debug_log, has_permission


class PermissionInspector(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		docname: DF.DynamicLink | None
		output: DF.Code | None
		permission_type: DF.Literal[
			"read",
			"write",
			"create",
			"delete",
			"submit",
			"cancel",
			"select",
			"amend",
			"print",
			"email",
			"report",
			"import",
			"export",
			"share",
		]
		ref_doctype: DF.Link
		user: DF.Link
	# end: auto-generated types

	@frappe.whitelist()
	def debug(self):
		if not (self.ref_doctype and self.user):
			return

		result = has_permission(
			self.ref_doctype, ptype=self.permission_type, doc=self.docname, user=self.user, debug=True
		)

		self.output = "\n==============================\n".join(_pop_debug_log())
		self.output += "\n\n" + f"Ouput of has_permission: {result}"

	# None of these apply, overriden for sanity.
	def load_from_db(self):
		super(Document, self).__init__({"modified": None, "permission_type": "read"})

	def db_insert(self, *args, **kwargs): ...

	def db_update(self): ...

	@staticmethod
	def get_list(): ...

	@staticmethod
	def get_count(): ...

	@staticmethod
	def get_stats(): ...

	def delete(self): ...
