# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class SystemHealthReportWorkers(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		count: DF.Int
		failed_jobs: DF.Int
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		queues: DF.Data | None
		utilization: DF.Percent
	# end: auto-generated types

	def db_insert(self, *args, **kwargs):
		raise NotImplementedError

	def load_from_db(self):
		raise NotImplementedError

	def db_update(self):
		raise NotImplementedError

	def delete(self):
		raise NotImplementedError

	@staticmethod
	def get_list(filters=None, page_length: int = 20, **kwargs) -> None:
		pass

	@staticmethod
	def get_count(filters=None, **kwargs) -> None:
		pass

	@staticmethod
	def get_stats(**kwargs) -> None:
		pass
