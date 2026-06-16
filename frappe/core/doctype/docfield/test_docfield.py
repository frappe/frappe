# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import json
import random
import string

import frappe
from frappe.tests import IntegrationTestCase


def _new_doctype_name():
	return "Test DynDesc " + "".join(random.sample(string.ascii_lowercase, 6))


def _resolve_description(config: dict, source_value) -> str:
	"""
	Python mirror of refresh_dynamic_description() in layout.js.

	Finds the first condition whose value matches source_value,
	or falls back to config["default"].
	"""
	if not config.get("source_field"):
		return config.get("default") or ""

	for cond in config.get("conditions") or []:
		if cond.get("value") == source_value:
			return cond.get("description") or ""

	return config.get("default") or ""


class TestDocFieldDynamicDescription(IntegrationTestCase):
	"""Tests for the dynamic_description feature on DocField."""

	created_doctypes: list[str] = []

	def tearDown(self):
		for name in self.created_doctypes:
			frappe.delete_doc_if_exists("DocType", name, force=True)
		self.created_doctypes.clear()
		frappe.db.rollback()

	# ------------------------------------------------------------------ #
	# Meta / schema tests                                                  #
	# ------------------------------------------------------------------ #

	def test_dynamic_description_field_exists_in_meta(self):
		"""dynamic_description is declared as a DocField property."""
		meta = frappe.get_meta("DocField")
		fieldnames = [f.fieldname for f in meta.fields]
		self.assertIn(
			"dynamic_description",
			fieldnames,
			"dynamic_description missing from DocField meta — run bench migrate",
		)

	def test_dynamic_description_is_hidden(self):
		"""dynamic_description should be hidden (managed via DynamicDescriptionEditor, not raw input)."""
		meta = frappe.get_meta("DocField")
		df = next(f for f in meta.fields if f.fieldname == "dynamic_description")
		self.assertEqual(df.hidden, 1)

	def test_dynamic_description_is_small_text(self):
		"""dynamic_description must be Small Text to hold arbitrary-length JSON."""
		meta = frappe.get_meta("DocField")
		df = next(f for f in meta.fields if f.fieldname == "dynamic_description")
		self.assertEqual(df.fieldtype, "Small Text")

	# ------------------------------------------------------------------ #
	# Persistence tests                                                    #
	# ------------------------------------------------------------------ #

	def test_dynamic_description_round_trips_through_db(self):
		"""A config stored on a field should survive insert → reload."""
		config = {
			"source_field": "customer_type",
			"conditions": [
				{"value": "Individual", "description": "NET30 applies."},
				{"value": "Company", "description": "NET60 terms."},
			],
			"default": "Standard terms apply.",
		}

		name = _new_doctype_name()
		self.created_doctypes.append(name)

		dt = frappe.get_doc(
			{
				"doctype": "DocType",
				"module": "Core",
				"custom": 1,
				"name": name,
				"fields": [
					{
						"label": "Customer Type",
						"fieldname": "customer_type",
						"fieldtype": "Select",
						"options": "Individual\nCompany",
					},
					{
						"label": "Payment Terms",
						"fieldname": "payment_terms",
						"fieldtype": "Data",
						"dynamic_description": json.dumps(config),
					},
				],
				"permissions": [{"role": "System Manager", "read": 1}],
			}
		).insert(ignore_permissions=True)

		dt.reload()

		payment_field = next(f for f in dt.fields if f.fieldname == "payment_terms")
		self.assertIsNotNone(payment_field.dynamic_description, "dynamic_description was not persisted")

		saved_config = json.loads(payment_field.dynamic_description)
		self.assertEqual(saved_config["source_field"], "customer_type")
		self.assertEqual(len(saved_config["conditions"]), 2)
		self.assertEqual(saved_config["conditions"][0]["value"], "Individual")
		self.assertEqual(saved_config["conditions"][1]["description"], "NET60 terms.")
		self.assertEqual(saved_config["default"], "Standard terms apply.")

	def test_dynamic_description_coexists_with_static_description(self):
		"""Both description and dynamic_description fields are independent."""
		config = {
			"source_field": "status",
			"conditions": [],
			"default": "Dynamic default",
		}

		name = _new_doctype_name()
		self.created_doctypes.append(name)

		dt = frappe.get_doc(
			{
				"doctype": "DocType",
				"module": "Core",
				"custom": 1,
				"name": name,
				"fields": [
					{
						"label": "Status",
						"fieldname": "status",
						"fieldtype": "Data",
						"description": "Static help text",
						"dynamic_description": json.dumps(config),
					}
				],
				"permissions": [{"role": "System Manager", "read": 1}],
			}
		).insert(ignore_permissions=True)

		dt.reload()
		field = next(f for f in dt.fields if f.fieldname == "status")

		self.assertEqual(field.description, "Static help text")
		saved = json.loads(field.dynamic_description)
		self.assertEqual(saved["default"], "Dynamic default")

	def test_dynamic_description_cleared_on_update(self):
		"""Removing dynamic_description (switching back to static) persists as empty."""
		config = {"source_field": "x", "conditions": [], "default": "D"}

		name = _new_doctype_name()
		self.created_doctypes.append(name)

		dt = frappe.get_doc(
			{
				"doctype": "DocType",
				"module": "Core",
				"custom": 1,
				"name": name,
				"fields": [
					{
						"label": "Field",
						"fieldname": "field",
						"fieldtype": "Data",
						"dynamic_description": json.dumps(config),
					}
				],
				"permissions": [{"role": "System Manager", "read": 1}],
			}
		).insert(ignore_permissions=True)

		# Now clear dynamic_description (user switched back to static)
		field_row = next(f for f in dt.fields if f.fieldname == "field")
		field_row.dynamic_description = ""
		dt.save(ignore_permissions=True)
		dt.reload()

		field_row = next(f for f in dt.fields if f.fieldname == "field")
		self.assertFalse(
			field_row.dynamic_description,
			"dynamic_description should be empty after switching to static mode",
		)

	def test_invalid_json_stored_and_retrieved_as_string(self):
		"""Malformed JSON is stored/returned as-is; JS side handles the parse error."""
		bad_json = "not { valid json"

		name = _new_doctype_name()
		self.created_doctypes.append(name)

		dt = frappe.get_doc(
			{
				"doctype": "DocType",
				"module": "Core",
				"custom": 1,
				"name": name,
				"fields": [
					{
						"label": "Field",
						"fieldname": "field",
						"fieldtype": "Data",
						"dynamic_description": bad_json,
					}
				],
				"permissions": [{"role": "System Manager", "read": 1}],
			}
		).insert(ignore_permissions=True)

		dt.reload()
		field = next(f for f in dt.fields if f.fieldname == "field")
		self.assertEqual(field.dynamic_description, bad_json)

	# ------------------------------------------------------------------ #
	# Resolution logic tests (mirrors refresh_dynamic_description in JS)  #
	# ------------------------------------------------------------------ #

	def test_resolve_matched_condition(self):
		"""Returns the description for the matching condition value."""
		config = {
			"source_field": "customer_type",
			"conditions": [
				{"value": "Individual", "description": "NET30 applies."},
				{"value": "Company", "description": "NET60 terms."},
			],
			"default": "Standard terms.",
		}
		self.assertEqual(_resolve_description(config, "Individual"), "NET30 applies.")
		self.assertEqual(_resolve_description(config, "Company"), "NET60 terms.")

	def test_resolve_falls_back_to_default_on_no_match(self):
		"""Unrecognised source value falls back to config['default']."""
		config = {
			"source_field": "customer_type",
			"conditions": [{"value": "Individual", "description": "NET30."}],
			"default": "Standard terms.",
		}
		self.assertEqual(_resolve_description(config, "Non-Profit"), "Standard terms.")

	def test_resolve_falls_back_to_default_on_none_value(self):
		"""None (unset field) falls back to default."""
		config = {
			"source_field": "customer_type",
			"conditions": [{"value": "Individual", "description": "NET30."}],
			"default": "Default text.",
		}
		self.assertEqual(_resolve_description(config, None), "Default text.")

	def test_resolve_falls_back_to_default_on_empty_string(self):
		"""Empty string source value falls back to default."""
		config = {
			"source_field": "customer_type",
			"conditions": [{"value": "Individual", "description": "NET30."}],
			"default": "Default text.",
		}
		self.assertEqual(_resolve_description(config, ""), "Default text.")

	def test_resolve_returns_empty_string_when_no_default(self):
		"""No matching condition and no default → empty string (no description shown)."""
		config = {
			"source_field": "customer_type",
			"conditions": [{"value": "Individual", "description": "NET30."}],
			"default": "",
		}
		self.assertEqual(_resolve_description(config, "Company"), "")

	def test_resolve_returns_default_when_no_source_field(self):
		"""Empty source_field config returns the default (pre-configured state)."""
		config = {"source_field": "", "conditions": [], "default": "Fallback."}
		self.assertEqual(_resolve_description(config, "anything"), "Fallback.")

	def test_resolve_returns_empty_when_no_source_field_and_no_default(self):
		"""Empty source_field and no default returns empty string."""
		config = {"source_field": "", "conditions": [], "default": ""}
		self.assertEqual(_resolve_description(config, "x"), "")

	def test_resolve_first_matching_condition_wins(self):
		"""If multiple conditions match (duplicate values), the first one wins."""
		config = {
			"source_field": "field",
			"conditions": [
				{"value": "A", "description": "First A."},
				{"value": "A", "description": "Second A."},
			],
			"default": "Default.",
		}
		self.assertEqual(_resolve_description(config, "A"), "First A.")

	def test_resolve_empty_conditions_list_uses_default(self):
		"""A dynamic config with no conditions always shows the default."""
		config = {
			"source_field": "status",
			"conditions": [],
			"default": "Always shown.",
		}
		self.assertEqual(_resolve_description(config, "Draft"), "Always shown.")
		self.assertEqual(_resolve_description(config, "Submitted"), "Always shown.")

	def test_resolve_matched_condition_with_empty_description(self):
		"""A condition with an empty description string returns empty (clears the help text)."""
		config = {
			"source_field": "field",
			"conditions": [{"value": "hide", "description": ""}],
			"default": "Default shown otherwise.",
		}
		self.assertEqual(_resolve_description(config, "hide"), "")
