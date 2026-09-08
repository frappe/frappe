# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

from typing import Any

import frappe
from frappe.tests import IntegrationTestCase

from flow.lib.model import Model


def _provider(**overrides: Any) -> dict:
	doc = {"doctype": "Flow Provider", "provider": "openrouter", "api_key": "sk-provider", "enabled": 1}
	doc.update(overrides)
	return doc


def _model(**overrides: Any) -> dict:
	doc = {
		"doctype": "Flow Model",
		"title": "Test Provider Model",
		"model_id": "openrouter/test/model",
		"enabled": 1,
	}
	doc.update(overrides)
	return doc


class TestFlowProviderValidation(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_inserts_with_known_provider(self):
		doc = frappe.get_doc(_provider()).insert()
		self.assertEqual(doc.name, "openrouter")

	def test_provider_name_normalized_lowercase(self):
		doc = frappe.get_doc(_provider(provider="OpenRouter")).insert()
		self.assertEqual(doc.provider, "openrouter")

	def test_unknown_provider_rejected(self):
		doc = frappe.get_doc(_provider(provider="not-a-real-provider"))
		with self.assertRaisesRegex(frappe.ValidationError, "Unknown provider"):
			doc.insert()

	def test_invalid_base_url_rejected(self):
		doc = frappe.get_doc(_provider(base_url="not-a-url"))
		with self.assertRaisesRegex(frappe.ValidationError, "Base URL"):
			doc.insert()


class TestProviderCredentialResolution(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_model_resolves_key_from_provider(self):
		frappe.get_doc(_provider(api_key="sk-from-provider")).insert()
		m = frappe.get_doc(_model()).insert()
		self.assertEqual(Model(m.name)._api_key, "sk-from-provider")

	def test_model_own_key_overrides_provider(self):
		frappe.get_doc(_provider(api_key="sk-from-provider")).insert()
		m = frappe.get_doc(_model(api_key="sk-on-model")).insert()
		self.assertEqual(Model(m.name)._api_key, "sk-on-model")

	def test_disabled_provider_not_used(self):
		frappe.get_doc(_provider(api_key="sk-from-provider", enabled=0)).insert()
		m = frappe.get_doc(_model()).insert()
		self.assertIsNone(Model(m.name)._api_key)

	def test_no_provider_row_leaves_key_empty(self):
		m = frappe.get_doc(_model()).insert()
		self.assertIsNone(Model(m.name)._api_key)

	def test_provider_base_url_used_when_model_has_none(self):
		frappe.get_doc(_provider(base_url="http://gateway.local")).insert()
		m = frappe.get_doc(_model()).insert()
		self.assertEqual(Model(m.name).base_url, "http://gateway.local")
