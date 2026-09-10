# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.tests import IntegrationTestCase

from flow.lib.model import model_config


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

	def test_the_config_carries_the_models_credentials(self):
		self.assertEqual(
			model_config(self.model.name),
			{"model": "openai/gpt-4o-mini", "api_key": "sk-model", "api_base": "http://gateway.local"},
		)

	def test_a_disabled_model_is_refused(self):
		self.model.db_set("enabled", 0)

		with self.assertRaisesRegex(frappe.ValidationError, "disabled"):
			model_config(self.model.name)
