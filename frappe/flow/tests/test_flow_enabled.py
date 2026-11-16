# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.flow import is_enabled
from frappe.flow.lib.model import SITE_PROVIDER, clear_enabled_cache
from frappe.flow.tests.test_permissions import _user
from frappe.tests import IntegrationTestCase

USER = "flow-enabled@example.com"
GROVE_KEY = [{"gateway_url": "https://grove.example.com", "api_key": "grove-key"}]


def delete_models_and_providers():
	for doctype in ("Flow Model", "Flow Provider"):
		for name in frappe.get_all(doctype, pluck="name"):
			frappe.delete_doc(doctype, name, force=True)
	clear_enabled_cache()


class TestFlowEnabled(IntegrationTestCase):
	def setUp(self):
		delete_models_and_providers()
		_user(USER)
		self.no_grove_key = patch.dict(frappe.conf, {"ai_keys": None})
		self.no_grove_key.start()

	def tearDown(self):
		self.no_grove_key.stop()
		frappe.set_user("Administrator")
		frappe.db.rollback()
		clear_enabled_cache()

	def _is_enabled(self) -> bool:
		with self.set_user(USER):
			return is_enabled()

	def _provider(self, provider: str = "openai"):
		return frappe.get_doc({"doctype": "Flow Provider", "provider": provider, "enabled": 1}).insert()

	def _model(self, **fields):
		return frappe.get_doc(
			{
				"doctype": "Flow Model",
				"title": "Enabled Check Model",
				"model_id": "openai/gpt-4o-mini",
				"enabled": 1,
				**fields,
			}
		).insert()

	def test_flow_is_enabled_with_a_provider_and_a_chat_model(self):
		self.assertFalse(self._is_enabled())

		self._provider()
		self.assertFalse(self._is_enabled())

		model = self._model()
		self.assertTrue(self._is_enabled())

		model.db_set("enabled", 0)
		self.assertFalse(self._is_enabled())

	def test_deleting_the_last_chat_model_disables_flow(self):
		self._provider()
		model = self._model()
		self.assertTrue(self._is_enabled())

		frappe.delete_doc("Flow Model", model.name, force=True)
		self.assertFalse(self._is_enabled())

	def test_a_model_with_its_own_key_needs_no_provider(self):
		self._model(api_key="sk-own")
		self.assertTrue(self._is_enabled())

	def test_another_providers_row_does_not_enable_a_model(self):
		self._provider("anthropic")
		self._model()
		self.assertFalse(self._is_enabled())

	def test_an_embedding_model_alone_does_not_enable_flow(self):
		self._provider()
		self._model(embedding=1)
		self.assertFalse(self._is_enabled())

	def test_a_grove_key_enables_flow_until_grove_is_turned_off(self):
		with patch.dict(frappe.conf, {"ai_keys": GROVE_KEY}):
			self.assertTrue(self._is_enabled())

			frappe.get_doc({"doctype": "Flow Provider", "provider": SITE_PROVIDER, "enabled": 0}).insert()
			self.assertFalse(self._is_enabled())
