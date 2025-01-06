# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt
from pathlib import Path

import frappe
from frappe.model.document import Document


class CustomScriptFile(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		code: DF.Code | None
	# end: auto-generated types

	def db_insert(self, *args, **kwargs):
		frappe.throw("Cannot create a new script from Desk")

	def load_from_db(self):
		script = Path(frappe.get_site_path()) / "private" / "custom_scripts" / self.name
		if not script.exists():
			raise frappe.DoesNotExistError

		super(Document, self).__init__(frappe._dict(name=self.name, code=script.read_text()))

	def db_update(self):
		raise NotImplementedError

	def delete(self):
		raise NotImplementedError

	@staticmethod
	def get_list(as_list: bool = False, *args, **kwargs) -> list:
		scripts = Path(frappe.get_site_path()) / "private" / "custom_scripts"
		if as_list:
			return [(script.name,) for script in scripts.glob("*.py")]
		return [frappe._dict(name=script.name) for script in scripts.glob("*.py")]

	@staticmethod
	def get_count(filters=None, **kwargs):
		scripts = Path(frappe.get_site_path()) / "private" / "custom_scripts"
		if scripts.exists():
			return len(list(scripts.iterdir()))
		return 0

	@staticmethod
	def get_stats(**kwargs):
		pass
