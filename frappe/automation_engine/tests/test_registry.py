# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import frappe
from frappe.automation_engine.registry import (
	clear_automation_cache,
	get_automations_for,
	get_custom_event_map,
)
from frappe.tests import IntegrationTestCase


def make_rule(document_type="ToDo", enabled=1, trigger_type="Doc Created", **kwargs):
	doc = frappe.new_doc("Automation Flow")
	doc.title = kwargs.pop("title", "Registry Rule")
	doc.trigger_type = trigger_type
	doc.document_type = document_type
	for key, value in kwargs.items():
		doc.set(key, value)
	doc.append("actions", {"action_type": "SetFieldValue", "params": '{"field": "priority", "value": "Low"}'})
	doc.enabled = enabled
	doc.insert()
	return doc


def make_enabled_custom_event_rule(custom_event="deal_won"):
	# Custom Event rules can't be enabled through the controller yet (no emitter is wired),
	# so flip `enabled` directly in the DB to exercise the registry's event-map build.
	doc = make_rule(trigger_type="Custom Event", document_type="ToDo", custom_event=custom_event, enabled=0)
	frappe.db.set_value("Automation Flow", doc.name, "enabled", 1, update_modified=False)
	return doc


class TestRegistry(IntegrationTestCase):
	def setUp(self):
		frappe.db.delete("Automation Flow")
		clear_automation_cache()

	def tearDown(self):
		frappe.db.rollback()
		clear_automation_cache()

	def test_build_returns_only_enabled(self):
		make_rule(title="on", enabled=1)
		make_rule(title="off", enabled=0)
		rules = get_automations_for("ToDo")
		self.assertEqual(len(rules), 1)
		self.assertEqual(rules[0].trigger_type, "Doc Created")

	def test_map_is_per_doctype(self):
		make_rule(document_type="ToDo")
		self.assertEqual(len(get_automations_for("ToDo")), 1)
		self.assertEqual(get_automations_for("User"), [])

	def test_empty_doctype_returns_empty_list(self):
		self.assertEqual(get_automations_for("User"), [])

	def test_save_invalidates_cache(self):
		self.assertEqual(get_automations_for("ToDo"), [])
		make_rule(title="added")
		self.assertEqual(len(get_automations_for("ToDo")), 1)

	def test_delete_invalidates_cache(self):
		rule = make_rule(title="temp")
		self.assertEqual(len(get_automations_for("ToDo")), 1)
		rule.delete()
		self.assertEqual(get_automations_for("ToDo"), [])

	def test_custom_event_map(self):
		make_enabled_custom_event_rule(custom_event="deal_won")
		event_map = get_custom_event_map()
		self.assertIn("deal_won", event_map)
		self.assertEqual(len(event_map["deal_won"]), 1)

	def test_custom_event_excluded_from_doc_map(self):
		make_enabled_custom_event_rule(custom_event="deal_won")
		self.assertEqual(get_automations_for("ToDo"), [])
