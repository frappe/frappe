# Copyright (c) 2023, Frappe Technologies and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class RecorderQuery(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		duration: DF.Float
		exact_copies: DF.Int
		explain_result: DF.Text | None
		index: DF.Int
		normalized_copies: DF.Int
		normalized_query: DF.Data | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		query: DF.Data | None
		stack: DF.Text | None
	# end: auto-generated types

	pass

	def db_insert(self, *args, **kwargs) -> None:
		pass

	def load_from_db(self) -> None:
		pass

	def db_update(self) -> None:
		pass

	@staticmethod
	def get_list() -> None:
		pass

	@staticmethod
	def get_count() -> None:
		pass

	@staticmethod
	def get_stats() -> None:
		pass

	def delete(self) -> None:
		pass
