# Copyright (c) 2023, Frappe Technologies and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.model.document import Document


class FormTourSettings(Document):
	def before_save(self):
		self.onboarding_tours = json.dumps(
			[[tour.form_tour, json.loads(tour.page_route)] for tour in self.form_tours]
		)


@frappe.whitelist()
def update_user_status(value, step):
	from frappe.utils.telemetry import capture

	step = frappe.parse_json(step)
	tour = frappe.parse_json(value)
	# from frappe.utils.telemetry import capture
	capture(
		frappe.scrub(f"{step.parent}_{step.title}"),
		app="frappe_ui_tours",
		properties={
			"is_completed": tour.is_completed
		},
	)
	frappe.db.set_value(
		"User", frappe.session.user, "onboarding_status", value, update_modified=False
	)
