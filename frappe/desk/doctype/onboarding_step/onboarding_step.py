# Copyright (c) 2020, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


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
	if step.action == "Create Entry":
		step.is_submittable = frappe.db.get_value(
			"DocType", step.reference_document, "is_submittable", cache=True
		)
	return step
