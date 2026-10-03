import inspect
from typing import Protocol, runtime_checkable

import frappe
from frappe import _
from frappe.model.base_document import get_controller
from frappe.model.document import Document


@runtime_checkable
class VirtualDoctype(Protocol):
	"""This class documents requirements that must be met by a doctype controller to function as virtual doctype


	Additional requirements:
	- DocType controller has to inherit from `frappe.model.document.Document` class

	Note:
	- "Backend" here means any storage service, it can be a database, flat file or network call to API.
	"""

	# ============ class/static methods ============

	@staticmethod
	def get_list(**kwargs) -> list[frappe._dict]:
		"""Similar to reportview.get_list"""
		...

	@staticmethod
	def get_count(**kwargs) -> int:
		"""Similar to reportview.get_count, return total count of documents on listview."""
		...

	@staticmethod
	def get_stats(**kwargs):
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


def validate_controller(doctype: str) -> None:
	try:
		controller = get_controller(doctype)
	except ImportError:
		frappe.msgprint(_("Failed to import virtual doctype {}, is controller file present?").format(doctype))
		return

	def _as_str(method):
		if hasattr(method, "__module__"):
			return f"{method.__module__}.{method.__qualname__}"
		return "None"

	expected_static_method = ["get_list", "get_count", "get_stats"]
	for m in expected_static_method:
		method = inspect.getattr_static(controller, m, None)
		if not isinstance(method, staticmethod):
			frappe.msgprint(
				_("Virtual DocType {} requires a static method called {} found {}").format(
					frappe.bold(doctype), frappe.bold(m), frappe.bold(_as_str(method))
				),
				title=_("Incomplete Virtual Doctype Implementation"),
			)

	# What counts as "overridden" is measured against `Document`, not against the controller's
	# immediate parent. A controller is free to inherit the contract from an intermediate base
	# that implements it for a whole family of doctypes -- a log-database base, an API-backed
	# base -- and that base's implementation is a real override even though the controller
	# itself declares nothing. Comparing with `controller.mro()[1]` saw only one level up, so
	# any such controller looked unimplemented and had to restate every method just to silence
	# the warning.
	#
	# `getattr` resolves each name through `Document`'s own MRO, so `load_from_db` and `delete`
	# come from `Document` while `db_insert` and `db_update` come from `BaseDocument`; either
	# way it is the default the controller must replace.
	expected_instance_methods = ["db_insert", "db_update", "load_from_db", "delete"]
	for m in expected_instance_methods:
		method = getattr(controller, m, None)
		default_method = getattr(Document, m, None)
		if method is default_method:
			frappe.msgprint(
				_("Virtual DocType {} requires overriding an instance method called {} found {}").format(
					frappe.bold(doctype), frappe.bold(m), frappe.bold(_as_str(method))
				),
				title=_("Incomplete Virtual Doctype Implementation"),
			)
