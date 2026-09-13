# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import frappe
from frappe.automation_engine.registry import clear_automation_cache
from frappe.automation_engine.relationships import (
	AutomationRelationshipProvider,
	get_relationship_definitions,
	query_related,
	resolve_one,
)
from frappe.tests import IntegrationTestCase

PROVIDER = "frappe.automation_engine.tests.test_schema_relationships.OverridingProvider"


class OverridingProvider(AutomationRelationshipProvider):
	"""Shadows a derived relationship, and renames another without reimplementing it."""

	def get_definitions(self, source_doctype):
		if source_doctype != "User":
			return []
		return [
			{
				"name": "todo_via_allocated_to",
				"label": "Assigned work",
				"cardinality": "many",
				"target_doctype": "ToDo",
			},
			{"name": "assigned", "derived_from": "todo_via_assigned_by", "label": "Delegated"},
		]

	def resolve(self, source_doc, relationship, params):
		return []


class BadRenameProvider(AutomationRelationshipProvider):
	def get_definitions(self, source_doctype):
		if source_doctype != "User":
			return []
		return [{"name": "x", "derived_from": "does_not_exist"}]

	def resolve(self, source_doc, relationship, params):
		return []


class TestSchemaRelationships(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		clear_automation_cache()
		# A site of any age has thousands of ToDos on Administrator, and queries are capped -
		# so every reverse-link assertion here runs against a user owning nothing else.
		self.user = self._user()

	def tearDown(self):
		frappe.db.rollback()
		clear_automation_cache()

	def _names(self, doctype) -> dict:
		return {item["name"]: item for item in get_relationship_definitions(doctype)}

	def _user(self):
		email = f"schema-rel-{frappe.generate_hash(length=8)}@example.com"
		return frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": "Schema Rel", "send_welcome_email": 0}
		).insert()

	def _note(self, title="schema rel note"):
		return frappe.get_doc({"doctype": "Note", "title": title, "content": title}).insert()

	def _todo(self, note, description="schema rel todo"):
		return frappe.get_doc(
			{
				"doctype": "ToDo",
				"description": description,
				"allocated_to": self.user.name,
				"assigned_by": self.user.name,
				"reference_type": "Note",
				"reference_name": note.name,
			}
		).insert()

	# derivation -----------------------------------------------------------
	def test_link_field_resolves_to_one_record(self):
		todo = self._todo(self._note())
		definition = self._names("ToDo")["allocated_to"]

		self.assertEqual(definition["cardinality"], "one")
		self.assertEqual(definition["target_doctype"], "User")
		self.assertEqual(resolve_one(todo, "allocated_to"), {"doctype": "User", "name": self.user.name})

	def test_dynamic_link_reads_its_target_from_the_record(self):
		note = self._note()
		todo = self._todo(note)

		self.assertIsNone(self._names("ToDo")["reference_name"]["target_doctype"])
		self.assertEqual(resolve_one(todo, "reference_name"), {"doctype": "Note", "name": note.name})

	def test_reverse_link_is_queryable_and_filterable(self):
		todo = self._todo(self._note(), "findable")
		user = frappe.get_doc("User", self.user.name)

		self.assertIn({"doctype": "ToDo", "name": todo.name}, query_related(user, "todo_via_allocated_to"))
		self.assertEqual(
			query_related(user, "todo_via_allocated_to", filters=[["description", "=", "nope"]]), []
		)

	def test_reverse_link_respects_the_row_limit(self):
		for index in range(3):
			self._todo(self._note(f"note {index}"), f"todo {index}")
		user = frappe.get_doc("User", self.user.name)

		self.assertEqual(len(query_related(user, "todo_via_allocated_to", limit=2)), 2)

	def test_dynamic_references_are_not_derived(self):
		"""They depend on data, not schema, so they stay an app's job to declare."""
		note = self._note()
		self._todo(note)

		self.assertNotIn("todo_via_reference_name", self._names("Note"))

	def test_bookkeeping_doctypes_are_not_offered(self):
		names = self._names("Note")

		self.assertFalse([name for name in names if name.startswith(("version_via", "comment_via"))])

	def test_ignore_hook_extends_the_deny_list(self):
		self.assertIn("todo_via_allocated_to", self._names("User"))

		with self.patch_hooks({"automation_relationship_ignore": ["ToDo"]}):
			clear_automation_cache()
			self.assertNotIn("todo_via_allocated_to", self._names("User"))

	# app overrides --------------------------------------------------------
	def test_app_definition_shadows_the_derived_one(self):
		self.assertTrue(self._names("User")["todo_via_allocated_to"]["derived"])

		with self.patch_hooks({"automation_relationships": [PROVIDER]}):
			clear_automation_cache()
			definition = self._names("User")["todo_via_allocated_to"]

		self.assertEqual(definition["label"], "Assigned work")
		self.assertFalse(definition.get("derived"))

	def test_rename_keeps_the_derived_resolution(self):
		todo = self._todo(self._note())

		with self.patch_hooks({"automation_relationships": [PROVIDER]}):
			clear_automation_cache()
			definition = self._names("User")["assigned"]
			related = query_related(frappe.get_doc("User", self.user.name), "assigned")

		self.assertEqual(definition["label"], "Delegated")
		self.assertEqual(definition["target_doctype"], "ToDo")
		self.assertIn({"doctype": "ToDo", "name": todo.name}, related)

	def test_rename_of_an_unknown_relationship_is_rejected(self):
		provider = f"{__name__}.BadRenameProvider"

		with self.patch_hooks({"automation_relationships": [provider]}):
			clear_automation_cache()
			with self.assertRaises(frappe.ValidationError):
				get_relationship_definitions("User")
