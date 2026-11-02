# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.flow.lib.model import model_config
from frappe.tests import IntegrationTestCase


class TestModelConfig(IntegrationTestCase):
	def setUp(self):
		self.model = frappe.get_doc(
			{
				"doctype": "Flow Model",
				"title": "Config Model",
				"model_id": "openai/gpt-4o-mini",
				"api_key": "sk-model",
				"base_url": "http://gateway.local",
				"enabled": 1,
			}
		).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_the_config_carries_the_models_settings_unless_it_is_disabled(self):
		self.assertEqual(
			model_config(self.model.name),
			{"model": "openai/gpt-4o-mini", "api_key": "sk-model", "api_base": "http://gateway.local"},
		)

		self.model.db_set("extra_params", '{"provider": {"zdr": true}}')
		self.assertEqual(model_config(self.model.name)["model_params"], {"provider": {"zdr": True}})

		self.model.db_set("enabled", 0)
		with self.assertRaisesRegex(frappe.ValidationError, "disabled"):
			model_config(self.model.name)
