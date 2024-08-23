# Copyright (c) 2020, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe import _
from frappe.model.document import Document


class OnboardingStep(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		action: DF.Literal[
			"Create Entry", "Update Settings", "Show Form Tour", "View Report", "Go to Page", "Watch Video"
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
def get_onboarding_steps(ob_steps):
	steps = []
	for s in json.loads(ob_steps):
		doc = frappe.get_doc("Onboarding Step", s.get("step"))
		step = doc.as_dict().copy()
		step.label = _(doc.title)
		if step.action == "Create Entry":
			step.is_submittable = frappe.db.get_value(
				"DocType", step.reference_document, "is_submittable", cache=True
			)
		steps.append(step)

	return steps
