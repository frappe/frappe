# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.automation_engine.registry import clear_automation_cache
from frappe.automation_engine.relationships import AutomationRelationshipProvider
from frappe.automation_engine.runner import execute_automation
from frappe.automation_engine.tests.test_runner import make_automation
from frappe.tests import IntegrationTestCase

PROVIDER = "frappe.automation_engine.tests.test_relationships.ToDoNoteProvider"


class ToDoNoteProvider(AutomationRelationshipProvider):
	"""ToDo <-> Note through ToDo's reference_type/reference_name pair."""

	def get_definitions(self, source_doctype):
		if source_doctype == "ToDo":
			return [{"name": "reference", "target_doctype": "Note", "cardinality": "one"}]
		if source_doctype == "Note":
			return [{"name": "todos", "target_doctype": "ToDo", "cardinality": "many"}]
		return []

	def resolve(self, source_doc, relationship, params):
		if relationship == "reference":
			return [{"doctype": source_doc.reference_type, "name": source_doc.reference_name}]
		names = frappe.get_all(
			"ToDo", {"reference_type": "Note", "reference_name": source_doc.name}, pluck="name"
		)
		return [{"doctype": "ToDo", "name": name} for name in names]


class TestRelationships(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.hooks = self.patch_hooks({"automation_relationships": [PROVIDER]})
		self.hooks.__enter__()
		clear_automation_cache()

	def tearDown(self):
		self.hooks.__exit__(None, None, None)
		frappe.db.rollback()
		clear_automation_cache()

	def test_action_updates_related_record_alias(self):
		note = self._note("before")
		todo = self._todo(note)
		auto = make_automation(
			[
				{
					"action_type": "SetFieldValue",
					"target": "note",
					"params": '{"field":"title","value":"after"}',
				}
			],
			relationships=json.dumps([{"alias": "note", "relationship": "reference"}]),
		)
		execute_automation(self._queue(auto, todo.name))
		self.assertEqual(frappe.db.get_value("Note", note.name, "title"), "after")

	def test_unknown_target_alias_is_rejected_on_save(self):
		self.assertRaisesRegex(
			frappe.ValidationError,
			"unknown target alias",
			make_automation,
			[{"action_type": "SetFieldValue", "target": "nope", "params": '{"field":"priority","value":"High"}'}],
		)

	def test_many_relationship_cannot_be_a_single_record_alias(self):
		self.assertRaisesRegex(
			frappe.ValidationError,
			"cannot be used as a single record alias",
			make_automation,
			[{"action_type": "SetFieldValue", "params": '{"field":"priority","value":"High"}'}],
			document_type="Note",
			relationships=json.dumps([{"alias": "todos", "relationship": "todos"}]),
		)

	def test_related_exists_condition_gates_the_step(self):
		note = self._note("source")
		todo = self._todo(note)
		condition = {"type": "RelatedExists", "source": "note", "relationship": "todos"}
		auto = make_automation(
			[
				{
					"action_type": "SetFieldValue",
					"params": '{"field":"priority","value":"High"}',
					"related_condition": json.dumps(condition),
				}
			],
			relationships=json.dumps([{"alias": "note", "relationship": "reference"}]),
		)
		execute_automation(self._queue(auto, todo.name))
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "priority"), "High")

	def test_related_not_exists_condition_skips_the_step(self):
		note = self._note("empty")
		todo = self._todo(note)
		condition = {
			"type": "RelatedNotExists",
			"source": "note",
			"relationship": "todos",
			"filters": [["description", "=", "nothing matches this"]],
		}
		auto = make_automation(
			[
				{
					"action_type": "SetFieldValue",
					"params": '{"field":"priority","value":"High"}',
					"related_condition": json.dumps(condition),
				}
			],
			relationships=json.dumps([{"alias": "note", "relationship": "reference"}]),
		)
		execute_automation(self._queue(auto, todo.name))
		# The Note has no ToDo with that description, so RelatedNotExists holds and the step ran.
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "priority"), "High")

	def test_condition_filters_render_against_an_aliased_record(self):
		note = self._note("templated")
		todo = self._todo(note)
		condition = {
			"type": "RelatedExists",
			"source": "note",
			"relationship": "todos",
			"filters": [["reference_name", "=", "{{ note.name }}"]],
		}
		auto = make_automation(
			[
				{
					"action_type": "SetFieldValue",
					"params": '{"field":"priority","value":"High"}',
					"related_condition": json.dumps(condition),
				}
			],
			relationships=json.dumps([{"alias": "note", "relationship": "reference"}]),
		)
		execute_automation(self._queue(auto, todo.name))
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "priority"), "High")

	def test_created_document_becomes_later_target(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "trigger"}).insert()
		auto = make_automation(
			[
				{
					"action_type": "CreateDocument",
					"output_alias": "created",
					"params": '{"doctype":"ToDo","values":{"description":"created"}}',
				},
				{
					"action_type": "SetFieldValue",
					"target": "created",
					"params": '{"field":"priority","value":"High"}',
				},
			]
		)
		execute_automation(self._queue(auto, todo.name))
		self.assertEqual(frappe.db.get_value("ToDo", {"description": "created"}, "priority"), "High")

	def test_output_alias_target_is_validated_against_its_doctype(self):
		"""CreateDocument declares what it produces, so a bad field on the alias fails on save."""
		self.assertRaisesRegex(
			frappe.ValidationError,
			"has no field",
			make_automation,
			[
				{
					"action_type": "CreateDocument",
					"output_alias": "created",
					"params": '{"doctype":"ToDo","values":{"description":"x"}}',
				},
				{
					"action_type": "SetFieldValue",
					"target": "created",
					"params": '{"field":"not_a_todo_field","value":"x"}',
				},
			],
		)

	def test_duplicate_output_alias_is_rejected(self):
		create = {
			"action_type": "CreateDocument",
			"output_alias": "created",
			"params": '{"doctype":"ToDo","values":{"description":"x"}}',
		}
		self.assertRaisesRegex(
			frappe.ValidationError, "duplicate output alias", make_automation, [create, dict(create)]
		)

	def test_output_alias_survives_wait_resume(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "trigger-wait"}).insert()
		auto = make_automation(
			[
				{
					"action_type": "CreateDocument",
					"output_alias": "created",
					"params": '{"doctype":"ToDo","values":{"description":"created-wait"}}',
				},
				{"step_type": "Wait", "params": '{"value":1,"unit":"Seconds"}'},
				{
					"action_type": "SetFieldValue",
					"target": "created",
					"params": '{"field":"priority","value":"High"}',
				},
			]
		)
		execute_automation(self._queue(auto, todo.name))
		resume = frappe.db.get_value(
			"Automation Trigger Queue", {"automation": auto, "resume_run": ("is", "set")}, "name"
		)
		execute_automation(resume)
		self.assertEqual(frappe.db.get_value("ToDo", {"description": "created-wait"}, "priority"), "High")

	def _note(self, title):
		return frappe.get_doc({"doctype": "Note", "title": title, "public": 1}).insert()

	def _todo(self, note):
		return frappe.get_doc(
			{
				"doctype": "ToDo",
				"description": "linked",
				"reference_type": "Note",
				"reference_name": note.name,
			}
		).insert()

	def _queue(self, automation, name):
		return (
			frappe.get_doc(
				{
					"doctype": "Automation Trigger Queue",
					"automation": automation,
					"ref_doctype": "ToDo",
					"ref_name": name,
					"status": "Pending",
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
