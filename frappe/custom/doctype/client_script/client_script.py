# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.model.document import Document


class ClientScript(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		dt: DF.Link
		enabled: DF.Check
		module: DF.Link | None
		script: DF.Code | None
		view: DF.Literal["List", "Form"]
	# end: auto-generated types

	def on_update(self):
		frappe.clear_cache(doctype=self.dt)

	def on_trash(self):
		frappe.clear_cache(doctype=self.dt)

	def before_save(self):
		script_exists = self.is_dt_script_already_exists()
		if script_exists:
			frappe.throw(f"Client Script for {self.dt} Doctype Already Exists")

	def is_dt_script_already_exists(self):
		return frappe.db.exists("Client Script", {"dt": self.dt})
