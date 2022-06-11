# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# License: MIT. See LICENSE

from typing import Protocol, runtime_checkable

import frappe
from frappe import _
from frappe.model.base_document import get_controller
from frappe.model.document import Document
from frappe.utils import cint
from frappe.utils.caching import site_cache


@runtime_checkable
class LogType(Protocol):
	"""Interface requirement for doctypes that can be cleared using log settings."""

	@staticmethod
	def clear_old_logs(days: int) -> None:
		...


@site_cache
def _supports_log_clearing(doctype: str) -> bool:
	try:
		controller = get_controller(doctype)
		return issubclass(controller, LogType)
	except Exception:
		return False


class LogSettings(Document):
	def validate(self):
		self.validate_supported_doctypes()
		self.validate_duplicates()

	def validate_supported_doctypes(self):
		for entry in self.logs_to_clear:
			if _supports_log_clearing(entry.ref_doctype):
				continue

			msg = _("{} does not support automated log clearing.").format(frappe.bold(entry.ref_doctype))
			if frappe.conf.developer_mode:
				msg += "<br>" + _("Implement `clear_old_logs` method to enable auto error clearing.")
			frappe.throw(msg, title=_("DocType not supported by Log Settings."))

	def validate_duplicates(self):
		seen = set()
		for entry in self.logs_to_clear:
			if entry.ref_doctype in seen:
				frappe.throw(
					_("{} appears more than once in configured log doctypes.").format(entry.ref_doctype)
				)
			seen.add(entry.ref_doctype)

	def clear_logs(self):
		"""
		Log settings can clear any log type that's registered to it and provides a method to delete old logs.

		Check `LogDoctype` above for interface that doctypes need to implement.
		"""

		for entry in self.logs_to_clear:
			controller: LogType = get_controller(entry.ref_doctype)
			func = controller.clear_old_logs

			# Only pass what the method can handle, this is considering any
			# future addition that might happen to the required interface.
			kwargs = frappe.get_newargs(func, {"days": entry.days})
			func(**kwargs)
			frappe.db.commit()

	def register_doctype(self, doctype: str, days=30):
		if doctype not in {d.ref_doctype for d in self.logs_to_clear}:
			self.append("logs_to_clear", {"ref_doctype": doctype, "days": cint(days)})


def run_log_clean_up():
	doc = frappe.get_doc("Log Settings")
	doc.clear_logs()


@frappe.whitelist()
def has_unseen_error_log():
	if frappe.get_all("Error Log", filters={"seen": 0}, limit=1):
		return {
			"show_alert": True,
			"message": _("You have unseen {0}").format(
				'<a href="/app/List/Error%20Log/List"> Error Logs </a>'
			),
		}


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_log_doctypes(doctype, txt, searchfield, start, page_len, filters):

	filters = filters or {}

	filters.extend(
		[
			["istable", "=", 0],
			["issingle", "=", 0],
			["name", "like", f"%%{txt}%%"],
		]
	)
	doctypes = frappe.get_list("DocType", filters=filters, pluck="name")

	supported_doctypes = [(d,) for d in doctypes if _supports_log_clearing(d)]

	return supported_doctypes[start:page_len]
