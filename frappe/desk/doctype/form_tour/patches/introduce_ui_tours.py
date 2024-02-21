import json

import frappe


def execute():
	"""Handle introduction of UI tours"""
	completed = {}
	for tour in frappe.get_all("Form Tour", {"ui_tour": 1}, pluck="name"):
		completed[tour] = {"is_complete": True}

	User = frappe.qb.DocType("User")
	frappe.qb.update(User).set("onboarding_status", json.dumps(completed)).run()
