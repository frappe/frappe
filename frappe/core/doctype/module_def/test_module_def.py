# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from unittest.mock import patch

import frappe
from frappe.model.sync import _get_schema_enabled_modules
from frappe.tests import IntegrationTestCase


class TestModuleDef(IntegrationTestCase):
	def _make_module(self, name, schema_enabled):
		module = frappe.new_doc("Module Def")
		module.module_name = name
		module.app_name = "frappe"
		module.schema_enabled = schema_enabled
		module.custom = 1  # prevents polluting modules.txt in developer_mode
		module.insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Module Def", name, force=True)
		return module

	def test_schema_disabled_module_excluded_from_sync(self):
		self._make_module("_Test Schema Disabled", schema_enabled=0)
		enabled = _get_schema_enabled_modules()
		self.assertNotIn("_test_schema_disabled", enabled)

	def test_schema_enabled_module_included_in_sync(self):
		self._make_module("_Test Schema Enabled", schema_enabled=1)
		enabled = _get_schema_enabled_modules()
		self.assertIn("_test_schema_enabled", enabled)

	def test_disabled_module_excluded_from_active_modules(self):
		from frappe.core.doctype.domain_settings.domain_settings import get_active_modules

		self._make_module("_Test Schema Hidden", schema_enabled=0)
		frappe.cache.delete_value("active_modules")
		self.addCleanup(frappe.cache.delete_value, "active_modules")

		self.assertNotIn("_Test Schema Hidden", get_active_modules())

	def test_enabling_schema_queues_sync_for(self):
		module = self._make_module("_Test Schema Sync", schema_enabled=0)
		module.reload()
		module.schema_enabled = 1

		with patch("frappe.model.sync.sync_for") as mock_sync_for:
			module._sync_module_schema()
			mock_sync_for.assert_called_once_with(module.app_name, modules={frappe.scrub(module.module_name)})

	def test_save_triggers_sync_on_schema_enable(self):
		module = self._make_module("_Test Schema Save Sync", schema_enabled=0)
		module.reload()
		module.schema_enabled = 1

		with patch("frappe.model.sync.sync_for") as mock_sync_for:
			frappe.db.after_commit.reset()
			module.save()
			frappe.db.after_commit.run()
			mock_sync_for.assert_called_once_with(module.app_name, modules={frappe.scrub(module.module_name)})

	def test_save_skips_sync_when_schema_unchanged(self):
		module = self._make_module("_Test Schema Save No Sync", schema_enabled=1)
		module.reload()

		with patch("frappe.model.sync.sync_for") as mock_sync_for:
			frappe.db.after_commit.reset()
			module.save()
			frappe.db.after_commit.run()
			mock_sync_for.assert_not_called()
