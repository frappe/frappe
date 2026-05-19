# Copyright (c) 2020, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.tests import IntegrationTestCase


class TestNumberCard(IntegrationTestCase):
	def test_report_card_hidden_when_report_is_not_allowed(self):
		user = "test2@example.com"
		report_name = "Test Restricted Number Card Report"
		card_name = "Test Restricted Report Number Card"
		baseline_role = "Desk User"
		exclusive_role = "System Manager"

		frappe.set_user("Administrator")
		frappe.delete_doc("Number Card", card_name, ignore_missing=True, force=True)
		frappe.delete_doc("Report", report_name, ignore_missing=True, force=True)
		self.addCleanup(lambda: frappe.delete_doc("Number Card", card_name, ignore_missing=True, force=True))
		self.addCleanup(lambda: frappe.delete_doc("Report", report_name, ignore_missing=True, force=True))

		user_doc = frappe.get_doc("User", user)
		had_baseline_role = baseline_role in frappe.get_roles(user)
		if not had_baseline_role:
			user_doc.add_roles(baseline_role)
			self.addCleanup(lambda: user_doc.remove_roles(baseline_role))

		had_exclusive_role = exclusive_role in frappe.get_roles(user)
		if had_exclusive_role:
			user_doc.remove_roles(exclusive_role)
			self.addCleanup(lambda: user_doc.add_roles(exclusive_role))

		report = frappe.get_doc(
			{
				"doctype": "Report",
				"report_name": report_name,
				"ref_doctype": "ToDo",
				"report_type": "Report Builder",
				"is_standard": "No",
				"roles": [{"role": exclusive_role}],
			}
		).insert(ignore_permissions=True)

		card = frappe.get_doc(
			{
				"doctype": "Number Card",
				"label": card_name,
				"type": "Report",
				"report_name": report.name,
				"function": "Count",
				"report_field": "name",
			}
		).insert(ignore_permissions=True)

		self.assertFalse(frappe.has_permission("Number Card", doc=card, user=user))
		self.assertNotIn(
			card.name,
			frappe.get_list("Number Card", filters={"name": card.name}, pluck="name", user=user),
		)
