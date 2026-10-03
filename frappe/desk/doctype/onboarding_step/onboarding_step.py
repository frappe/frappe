# Copyright (c) 2020, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr


class OnboardingStep(Document):
	_DOCTYPE_NAME = "Onboarding Step"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		action: DF.Literal[
			"Create Entry", "Update Settings", "Show Form Tour", "View Report", "Go to Page", "View Docs"
		]
		action_label: DF.Data | None
		callback_message: DF.SmallText | None
		callback_title: DF.Data | None
		description: DF.MarkdownEditor | None
		field: DF.Literal[None]
		form_tour: DF.Link | None
		intro_video_url: DF.Data | None
		is_complete: DF.Check
		is_single: DF.Check
		is_skipped: DF.Check
		path: DF.Data | None
		reference_document: DF.Link | None
		reference_report: DF.Link | None
		report_description: DF.Data | None
		report_reference_doctype: DF.Data | None
		report_type: DF.Data | None
		route_options: DF.Code | None
		show_form_tour: DF.Check
		show_full_form: DF.Check
		title: DF.Data
		validate_action: DF.Check
		value_to_validate: DF.Data | None
		video_url: DF.Data | None
	# end: auto-generated types

	def before_export(self, doc):
		doc.is_complete = 0
		doc.is_skipped = 0

	def is_done(self) -> bool:
		"""Ticked off, skipped, or its work already done some other way."""
		return bool(self.is_complete or self.is_skipped or self.is_work_done())

	def is_work_done(self) -> bool | None:
		"""Whether what the step asks for has been done, for the steps where that can be read.

		`None` means there is nothing to read: opening a page, a report or a tour is the step itself.
		A record counts whoever made it, so a Company from the setup wizard or Customers from an
		import finish their steps without anyone opening the onboarding.
		"""
		doctype = self.reference_document
		if not doctype or not frappe.db.exists("DocType", doctype):
			return None

		# Every site has users nobody invited: Administrator, Guest and whoever ran the setup
		# wizard. A user existing says nothing about the team being invited.
		if doctype == "User":
			return None

		meta = frappe.get_meta(doctype)
		if self.action == "Create Entry" and not meta.issingle:
			filters = {"docstatus": 1} if meta.is_submittable else None
			return bool(frappe.get_all(doctype, filters=filters, limit=1, pluck="name"))

		if self.action == "Update Settings" and self.validate_action and self.field and meta.issingle:
			value = frappe.db.get_single_value(doctype, self.field)
			if self.value_to_validate == "%":
				return bool(value)
			return cstr(value) == cstr(self.value_to_validate)

		return None

	def throw_if_unfinished(self):
		if self.is_work_done() is not False:
			return

		doctype = _(self.reference_document)
		if self.action == "Update Settings":
			label = _(frappe.get_meta(self.reference_document).get_label(self.field))
			frappe.throw(_("Set {0} in {1} to finish this step.").format(label, doctype))
		elif frappe.get_meta(self.reference_document).is_submittable:
			frappe.throw(_("Submit a {0} to finish this step.").format(doctype))
		else:
			frappe.throw(_("Create a {0} to finish this step.").format(doctype))


@frappe.whitelist()
def get_onboarding_steps(ob_steps: str | list):
	return [get_step_details(s.get("step")) for s in frappe.parse_json(ob_steps)]


def get_step_details(name: str) -> dict:
	"""A step as the onboarding widget renders it, with its text translated."""
	doc = frappe.get_doc("Onboarding Step", name)
	step = doc.as_dict().copy()
	step.label = _(doc.title)
	step.title = _(doc.title)
	step.description = _(doc.description) if doc.description else None
	step.action_label = _(doc.action_label) if doc.action_label else None
	step.is_complete = int(bool(doc.is_complete or doc.is_work_done()))
	if step.action == "Create Entry":
		step.is_submittable = frappe.db.get_value(
			"DocType", step.reference_document, "is_submittable", cache=True
		)
	return step
