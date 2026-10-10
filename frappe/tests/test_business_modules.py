# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from contextlib import contextmanager
from typing import ClassVar
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.business_modules import (
	HOOK_NAME,
	get_business_module_names,
	get_business_modules,
	validate_show_for_module,
)


@contextmanager
def registered_modules(hooks_by_app: dict[str, list]):
	"""Fake the business_modules hooks for one test. Apps in the dict are added to the installed apps."""
	real_get_hooks = frappe.get_hooks
	# keep the real apps in the list, their other hooks still run during a test
	apps = frappe.get_installed_apps()
	apps += [app for app in hooks_by_app if app not in apps]

	def fake_get_hooks(hook=None, *args, **kwargs):
		if hook == HOOK_NAME:
			return list(hooks_by_app.get(kwargs.get("app_name"), []))
		return real_get_hooks(hook, *args, **kwargs)

	frappe.local.request_cache.clear()
	try:
		with (
			patch.object(frappe, "get_installed_apps", return_value=apps),
			patch.object(frappe, "get_hooks", side_effect=fake_get_hooks),
		):
			yield
	finally:
		frappe.local.request_cache.clear()


class TestBusinessModules(IntegrationTestCase):
	def test_no_hooks_gives_empty_list(self):
		with registered_modules({"frappe": []}):
			self.assertEqual(get_business_modules(), [])
			self.assertEqual(get_business_module_names(), [])

	def test_collects_modules_from_all_apps_in_install_order(self):
		hooks = {
			"frappe": [],
			"app_one": [
				{"module": "Stock", "fieldname": "stock"},
				{"module": "Manufacturing", "fieldname": "manufacturing"},
			],
			"app_two": [{"module": "Payroll", "fieldname": "payroll"}],
		}
		with registered_modules(hooks):
			modules = get_business_modules()

		self.assertEqual([m["module"] for m in modules], ["Stock", "Manufacturing", "Payroll"])
		self.assertEqual(
			modules[1], {"module": "Manufacturing", "fieldname": "manufacturing", "app": "app_one"}
		)
		self.assertEqual(modules[2]["app"], "app_two")

	def test_first_app_wins_on_duplicate_module_name(self):
		hooks = {
			"app_one": [{"module": "Stock", "fieldname": "stock"}],
			"app_two": [
				{"module": "Stock", "fieldname": "stock_other"},
				{"module": "Loans", "fieldname": "loans"},
			],
		}
		with registered_modules(hooks):
			modules = get_business_modules()

		self.assertEqual([m["module"] for m in modules], ["Stock", "Loans"])
		self.assertEqual(modules[0]["fieldname"], "stock")
		self.assertEqual(modules[0]["app"], "app_one")

	def test_invalid_entries_are_skipped_not_raised(self):
		hooks = {
			"app_one": [
				"Stock",  # not a dict
				{"fieldname": "no_name"},  # missing module
				{"module": "   ", "fieldname": "blank"},  # blank module
				{"module": "Bad Field", "fieldname": "Not-Valid"},  # bad fieldname
				{"module": " Assets ", "fieldname": "assets"},  # valid, name gets trimmed
			]
		}
		with registered_modules(hooks):
			modules = get_business_modules()

		self.assertEqual(modules, [{"module": "Assets", "fieldname": "assets", "app": "app_one"}])

	def test_boot_carries_business_modules(self):
		from frappe.boot import get_bootinfo

		# Boot loads other hooks from real apps, so register under frappe, which is real.
		with registered_modules({"frappe": [{"module": "Stock", "fieldname": "stock"}]}):
			bootinfo = get_bootinfo()

		self.assertEqual([m["module"] for m in bootinfo.business_modules], ["Stock"])


class CustomizationTestCase(IntegrationTestCase):
	"""Tests that make Custom Fields and Property Setters on Event."""

	def setUp(self):
		# Skip the table change, so a rollback can undo everything a test made.
		self.enterContext(patch.object(frappe.db, "updatedb"))
		self.enterContext(self.set_user("test@example.com"))

	def tearDown(self):
		frappe.db.rollback()
		frappe.clear_cache(doctype="Event")
		frappe.flags.in_migrate = False


class TestBusinessModuleProperty(CustomizationTestCase):
	"""The "Business Module" property on DocField, Customize Form and Custom Field."""

	MODULES: ClassVar[dict] = {"frappe": [{"module": "Stock", "fieldname": "stock"}]}
	FIELD = "description"  # a plain, optional field on Event

	def test_customize_form_allows_the_property(self):
		from frappe.custom.doctype.customize_form.customize_form import docfield_properties

		self.assertEqual(docfield_properties.get("show_for_module"), "Data")

	def test_customize_form_saves_it_and_meta_shows_it(self):
		with registered_modules(self.MODULES):
			d = frappe.get_doc("Customize Form")
			d.doc_type = "Event"
			d.run_method("fetch_to_customize")
			d.get("fields", {"fieldname": self.FIELD})[0].show_for_module = "Stock"
			d.run_method("save_customization")

		saved = frappe.db.get_value(
			"Property Setter",
			{"doc_type": "Event", "field_name": self.FIELD, "property": "show_for_module"},
			"value",
		)
		self.assertEqual(saved, "Stock")
		self.assertEqual(frappe.get_meta("Event").get_field(self.FIELD).show_for_module, "Stock")

	def test_custom_field_carries_it(self):
		with registered_modules(self.MODULES):
			frappe.get_doc(
				{
					"doctype": "Custom Field",
					"dt": "Event",
					"fieldname": "test_bm_custom",
					"label": "Test BM Custom",
					"fieldtype": "Data",
					"show_for_module": "Stock",
				}
			).insert()

		self.assertEqual(frappe.get_meta("Event").get_field("test_bm_custom").show_for_module, "Stock")


class TestShowForModuleSaveRules(CustomizationTestCase):
	"""Saving a field checks its Show for Module value."""

	MODULES: ClassVar[dict] = {"frappe": [{"module": "Stock", "fieldname": "stock"}]}

	def customize_event(self, fieldname="description", **values):
		d = frappe.get_doc("Customize Form")
		d.doc_type = "Event"
		d.run_method("fetch_to_customize")
		d.get("fields", {"fieldname": fieldname})[0].update(values)
		d.run_method("save_customization")
		return d

	def custom_field(self, **values):
		doc = frappe.get_doc(
			{
				"doctype": "Custom Field",
				"dt": "Event",
				"fieldname": "test_bm_rules",
				"label": "Test BM Rules",
				"fieldtype": "Data",
				**values,
			}
		)
		doc.insert()
		return doc

	def cleared_message_shown(self):
		return any("cleared" in (m.get("message") or "") for m in frappe.local.message_log)

	# rule 1: the module must be registered

	def test_unknown_module_rejected_in_customize_form(self):
		with registered_modules(self.MODULES), self.assertRaises(frappe.ValidationError):
			self.customize_event(show_for_module="Stok")

	def test_unknown_module_rejected_in_custom_field(self):
		with registered_modules(self.MODULES), self.assertRaises(frappe.ValidationError):
			self.custom_field(show_for_module="Stok")

	def test_unknown_module_rejected_on_doctype_save(self):
		# DocType save calls validate_show_for_module on every field. Check it directly,
		# so the test does not have to create a real DocType (which cannot be rolled back).
		field = frappe.new_doc("DocField")
		field.update({"fieldname": "f", "label": "F", "fieldtype": "Data", "show_for_module": "Stok"})
		with registered_modules(self.MODULES), self.assertRaises(frappe.ValidationError):
			validate_show_for_module(field, "Some DocType")

	def test_unknown_module_does_not_block_other_custom_fields(self):
		with registered_modules(self.MODULES):
			self.custom_field(show_for_module="Stock")
		# the app that registered Stock is uninstalled
		with registered_modules({"frappe": []}):
			frappe.get_doc(
				{
					"doctype": "Custom Field",
					"dt": "Event",
					"fieldname": "test_bm_other",
					"label": "Test BM Other",
					"fieldtype": "Data",
				}
			).insert()

	def test_known_module_is_accepted(self):
		with registered_modules(self.MODULES):
			doc = self.custom_field(show_for_module="Stock")
		self.assertEqual(doc.show_for_module, "Stock")

	def test_unknown_module_allowed_during_migrate(self):
		# An app's own modules are not "installed" yet while its doctypes sync.
		frappe.flags.in_migrate = True
		with registered_modules(self.MODULES):
			doc = self.custom_field(show_for_module="Not Yet Registered")
		self.assertEqual(doc.show_for_module, "Not Yet Registered")

	# rule 2: mandatory fields cannot have a module

	def test_mandatory_clears_module_in_custom_field(self):
		with registered_modules(self.MODULES):
			doc = self.custom_field(show_for_module="Stock", reqd=1)
		self.assertFalse(doc.show_for_module)
		self.assertTrue(self.cleared_message_shown())

	def test_mandatory_depends_on_clears_module_in_custom_field(self):
		with registered_modules(self.MODULES):
			doc = self.custom_field(show_for_module="Stock", mandatory_depends_on="eval:doc.subject")
		self.assertFalse(doc.show_for_module)

	def test_making_field_mandatory_later_clears_module(self):
		with registered_modules(self.MODULES):
			doc = self.custom_field(show_for_module="Stock")
			self.assertEqual(doc.show_for_module, "Stock")
			doc.reqd = 1
			doc.save()
		self.assertFalse(doc.show_for_module)

	def test_mandatory_clears_module_in_customize_form(self):
		with registered_modules(self.MODULES):
			self.customize_event(show_for_module="Stock", reqd=1)
		self.assertFalse(frappe.get_meta("Event").get_field("description").show_for_module)
		self.assertTrue(self.cleared_message_shown())

	def test_mandatory_clears_module_of_custom_field_in_customize_form(self):
		with registered_modules(self.MODULES):
			self.custom_field()
			self.customize_event("test_bm_rules", show_for_module="Stock", reqd=1)
		saved = frappe.db.get_value(
			"Custom Field", {"dt": "Event", "fieldname": "test_bm_rules"}, "show_for_module"
		)
		self.assertFalse(saved)

	def test_unsetting_mandatory_does_not_bring_module_back(self):
		with registered_modules(self.MODULES):
			doc = self.custom_field(show_for_module="Stock", reqd=1)
			doc.reqd = 0
			doc.save()
		self.assertFalse(doc.show_for_module)
