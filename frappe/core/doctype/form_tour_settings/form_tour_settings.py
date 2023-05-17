# Copyright (c) 2023, Frappe Technologies and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.model.document import Document


class FormTourSettings(Document):
	def on_update(self):
		onboarding_tours = [[tour.form_tour, json.loads(tour.page_route)] for tour in self.form_tours]
		frappe.db.set_single_value(
			"Form Tour Settings", "onboarding_tours", json.dumps(onboarding_tours)
		)
