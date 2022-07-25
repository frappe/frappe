from typing import Protocol

import frappe


class VirtualDoctype(Protocol):
	"""This class documents requirements that must be met by a doctype controller to function as virtual doctype


	Additional requirements:
	- DocType controller has to inherit from `frappe.model.document.Document` class

	Note:
	- "Backend" here means any storage service, it can be a database, flat file or network call to API.
	"""

	# ============ class/static methods ============

	@staticmethod
	def get_list(args) -> list[frappe._dict]:
		"""Similar to reportview.get_list"""
		...

	@staticmethod
	def get_count(args) -> int:
		"""Similar to reportview.get_count, return total count of documents on listview."""
		...

	@staticmethod
	def get_stats(args):
		"""Similar to reportview.get_stats, return sidebar stats."""
		...

	# ============ instance methods ============

	def db_insert(self, *args, **kwargs) -> None:
		"""Serialize the `Document` object and insert it in backend."""
		...

	def load_from_db(self) -> None:
		"""Using self.name initialize current document from backend data.

		This is responsible for updatinng __dict__ of class with all the fields on doctype."""
		...

	def db_update(self, *args, **kwargs) -> None:
		"""Serialize the `Document` object and update existing document in backend."""
		...

	def delete(self, *args, **kwargs) -> None:
		"""Delete the current document from backend"""
		...
