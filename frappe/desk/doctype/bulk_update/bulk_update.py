# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

import re

import frappe
from frappe import _
from frappe.core.doctype.submission_queue.submission_queue import queue_submission
from frappe.model.document import Document
from frappe.utils import cint, flt
from frappe.utils.scheduler import is_scheduler_inactive


class BulkUpdate(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		condition: DF.SmallText | None
		document_type: DF.Link
		field: DF.Literal[None]
		limit: DF.Int
		update_value: DF.SmallText
	# end: auto-generated types

	def validate(self):
		validate_formula(self.doctype, self.field, self.update_value)

	@frappe.whitelist()
	def bulk_update(self):
		self.check_permission("write")
		limit = self.limit if self.limit and cint(self.limit) < 500 else 500

		condition = ""
		if self.condition:
			if ";" in self.condition:
				frappe.throw(_("; not allowed in condition"))

			condition = f" where {self.condition}"

		docnames = frappe.db.sql_list(
			f"""select name from `tab{self.document_type}`{condition} limit {limit} offset 0"""
		)
		return submit_cancel_or_update_docs(
			self.document_type, docnames, "update", {self.field: self.update_value}
		)


@frappe.whitelist()
def submit_cancel_or_update_docs(doctype, docnames, action="submit", data=None, task_id=None):
	if isinstance(docnames, str):
		docnames = frappe.parse_json(docnames)

	if len(docnames) < 20:
		return _bulk_action(doctype, docnames, action, data, task_id)
	elif len(docnames) <= 500:
		frappe.msgprint(_("Bulk operation is enqueued in background."), alert=True)
		frappe.enqueue(
			_bulk_action,
			doctype=doctype,
			docnames=docnames,
			action=action,
			data=data,
			task_id=task_id,
			queue="short",
			timeout=1000,
		)
	else:
		frappe.throw(_("Bulk operations only support up to 500 documents."), title=_("Too Many Documents"))


def _bulk_action(doctype, docnames, action, data, task_id=None):
	if data:
		data = frappe.parse_json(data)

	failed = []
	num_documents = len(docnames)

	for idx, docname in enumerate(docnames, 1):
		doc = frappe.get_doc(doctype, docname)
		try:
			message = ""
			if action == "submit" and doc.docstatus.is_draft():
				if doc.meta.queue_in_background and not is_scheduler_inactive():
					queue_submission(doc, action)
					message = _("Queuing {0} for Submission").format(doctype)
				else:
					doc.submit()
					message = _("Submitting {0}").format(doctype)
			elif action == "cancel" and doc.docstatus.is_submitted():
				doc.cancel()
				message = _("Cancelling {0}").format(doctype)
			elif action == "update" and not doc.docstatus.is_cancelled():
				for field, val in data.items():
					val = apply_formula(doc, field, val)
					doc.set(field, val)
				doc.save()
				message = _("Updating {0}").format(doctype)
			else:
				failed.append(docname)
			frappe.db.commit()
			frappe.publish_progress(
				percent=idx / num_documents * 100,
				title=message,
				description=docname,
				task_id=task_id,
			)

		except Exception:
			failed.append(docname)
			frappe.db.rollback()

	return failed


from frappe.deprecation_dumpster import show_progress

NUMERIC_PATTERN = re.compile(r"^-?\d+(\.\d+)?$")


def apply_formula(doc: Document | dict, field: str, update_value: str | int | float | None) -> float:
	"""
	Apply numeric or formula-based updates to a field value.

	Supports:
	- Plain numbers: 123, 45.6
	- Short formulas: =+10, =*2, =/3
	- Expressions with 'current': =(current+20)

	Args:
		doc (Union[Document, dict]): Frappe document or dict containing the field.
		field (str): Field name to update.
		update_value (Union[str, int, float, None]): Number or formula as string.

	Returns:
		float: Updated value after applying the formula.
	"""

	if not update_value:
		return update_value

	if not isinstance(update_value, str):
		return update_value  # ignore non-string inputs

	update_value = update_value.strip()
	current_val = flt(doc.get(field) or 0)

	# Allow plain numbers
	if NUMERIC_PATTERN.fullmatch(update_value):
		return flt(update_value)

	# Formulas must start with '='
	if not update_value.startswith("="):
		frappe.throw(
			_("Invalid input. Please enter a number or a formula (e.g. 123, =+10, =*2, =(current+20))")
		)

	formula = update_value[1:].strip()
	if not formula:
		frappe.throw(_("Formula cannot be empty. Example: =+10, =*2, =(current+20)"))

	if formula[0] in ["+", "-", "*", "/", "%"]:
		operand_str = formula[1:].strip()
		if not NUMERIC_PATTERN.fullmatch(operand_str):
			frappe.throw(_("Invalid formula. Example: =+10, =*2, =(current+20)"))

		operand = flt(operand_str)

		if formula[0] == "+":
			return current_val + operand
		if formula[0] == "-":
			return current_val - operand
		if formula[0] == "*":
			return current_val * operand
		if formula[0] == "/":
			if operand == 0:
				frappe.throw(_("Division by zero is not allowed"))
			return current_val / operand
		if formula[0] == "%":
			if operand == 0:
				frappe.throw(_("Modulo by zero is not allowed"))
			return current_val % operand

	try:
		return frappe.safe_eval(formula, {"current": current_val})
	except Exception:
		frappe.throw(_("Invalid formula. Example: =+10, =*2, =(current+20)"))


@frappe.whitelist()
def validate_formula(doctype: str, field: str, value: str) -> bool:
	"""Validate a formula"""
	if not value or not isinstance(value, str):
		return True

	if value.strip() == "=":
		frappe.throw(_("Formula cannot be empty. Example: =+10, =*2, =(current+20)"))

	doc = frappe.new_doc(doctype)
	apply_formula(doc, field, value)

	return True
