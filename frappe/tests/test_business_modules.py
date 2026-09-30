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
)


@contextmanager
def registered_modules(hooks_by_app: dict[str, list]):
	"""Fake the installed apps and their business_modules hooks for one test."""
	real_get_hooks = frappe.get_hooks

	def fake_get_hooks(hook=None, *args, **kwargs):
		if hook == HOOK_NAME:
			return list(hooks_by_app.get(kwargs.get("app_name"), []))
		return real_get_hooks(hook, *args, **kwargs)

	frappe.local.request_cache.clear()
	try:
		with (
			patch.object(frappe, "get_installed_apps", return_value=list(hooks_by_app)),
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


class TestBusinessModuleProperty(IntegrationTestCase):
	"""The "Business Module" property on DocField, Customize Form and Custom Field."""

	MODULES: ClassVar[dict] = {"frappe": [{"module": "Stock", "fieldname": "stock"}]}
	FIELD = "description"  # a plain, optional field on Event

	def tearDown(self):
		frappe.db.delete("Property Setter", {"doc_type": "Event", "field_name": self.FIELD})
		frappe.db.delete("Custom Field", {"dt": "Event", "fieldname": "test_bm_custom"})
		if frappe.db.exists("DocType", "Test BM DocType"):
			frappe.delete_doc("DocType", "Test BM DocType", force=True)
		frappe.clear_cache(doctype="Event")

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

	def test_doctype_field_carries_it(self):
		with registered_modules(self.MODULES):
			frappe.get_doc(
				{
					"doctype": "DocType",
					"name": "Test BM DocType",
					"module": "Custom",
					"custom": 1,
					"fields": [
						{"fieldname": "plain", "label": "Plain", "fieldtype": "Data"},
						{
							"fieldname": "tagged",
							"label": "Tagged",
							"fieldtype": "Data",
							"show_for_module": "Stock",
						},
					],
				}
			).insert()

		meta = frappe.get_meta("Test BM DocType")
		self.assertEqual(meta.get_field("tagged").show_for_module, "Stock")
		self.assertFalse(meta.get_field("plain").show_for_module)
