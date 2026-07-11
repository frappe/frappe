# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import frappe
from frappe.automation_engine.dispatch import run_automations
from frappe.automation_engine.registry import clear_automation_cache, get_automations_for
from frappe.tests import IntegrationTestCase


def make_automation(trigger_type="Doc Created", **kwargs):
	doc = frappe.new_doc("Automation")
	doc.title = kwargs.pop("title", "Dispatch Rule")
	doc.trigger_type = trigger_type
	doc.document_type = "ToDo"
	for key, value in kwargs.items():
		doc.set(key, value)
	doc.append("actions", {"action_type": "SetFieldValue", "params": '{"field": "priority", "value": "Low"}'})
	doc.enabled = 1
	doc.insert()
	return doc


def make_todo(**kwargs):
	return frappe.get_doc({"doctype": "ToDo", "description": "x", **kwargs}).insert()


def pending(automation):
	return frappe.get_all("Automation Trigger Queue", filters={"automation": automation, "status": "Pending"})


class TestDispatch(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.delete("Automation Trigger Queue")
		frappe.db.delete("Automation")
		clear_automation_cache()

	def tearDown(self):
		frappe.db.rollback()
		clear_automation_cache()

	def test_doc_created_queues_a_row(self):
		rule = make_automation("Doc Created")
		todo = make_todo()
		rows = pending(rule.name)
		self.assertEqual(len(rows), 1)
		row = frappe.get_doc("Automation Trigger Queue", rows[0].name)
		self.assertEqual(row.ref_doctype, "ToDo")
		self.assertEqual(row.ref_name, todo.name)

	def test_doc_updated_ignores_insert_fires_on_save(self):
		rule = make_automation("Doc Updated")
		todo = make_todo()
		self.assertEqual(len(pending(rule.name)), 0)
		todo.description = "changed"
		todo.save()
		self.assertEqual(len(pending(rule.name)), 1)

	def test_field_value_changed_from_to(self):
		rule = make_automation(
			"Field Value Changed", trigger_field="status", from_value="Open", to_value="Closed"
		)
		todo = make_todo()
		self.assertEqual(len(pending(rule.name)), 0)
		todo.status = "Closed"
		todo.save()
		self.assertEqual(len(pending(rule.name)), 1)

	def test_field_value_changed_to_value_mismatch(self):
		rule = make_automation(
			"Field Value Changed", trigger_field="status", from_value="Open", to_value="Closed"
		)
		todo = make_todo()
		todo.status = "Cancelled"
		todo.save()
		self.assertEqual(len(pending(rule.name)), 0)

	def test_filters_gate_the_match(self):
		rule = make_automation("Doc Created", filters='[["priority", "=", "High"]]')
		make_todo(priority="Low")
		self.assertEqual(len(pending(rule.name)), 0)
		make_todo(priority="High")
		self.assertEqual(len(pending(rule.name)), 1)

	def test_condition_gates_the_match(self):
		rule = make_automation("Doc Created", condition="doc.priority == 'High'")
		make_todo(priority="Low")
		self.assertEqual(len(pending(rule.name)), 0)
		make_todo(priority="High")
		self.assertEqual(len(pending(rule.name)), 1)

	def test_skip_automations_flag(self):
		rule = make_automation("Doc Created")
		frappe.flags.skip_automations = True
		try:
			make_todo()
		finally:
			frappe.flags.skip_automations = False
		self.assertEqual(len(pending(rule.name)), 0)

	def test_zero_overhead_for_unautomated_doctype(self):
		# Warm the (empty) cache so the no-op path is a local dict hit.
		self.assertEqual(get_automations_for("User"), [])
		user = frappe.get_doc("User", "Administrator")
		with self.assertQueryCount(0):
			run_automations(user, "on_update")
