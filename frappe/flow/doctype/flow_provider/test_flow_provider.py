# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

from typing import Any

import frappe
from frappe.flow.lib.model import model_config
from frappe.tests import IntegrationTestCase


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

	def test_a_provider_is_a_known_litellm_name_with_an_http_base_url(self):
		for overrides, error in (
			({"provider": "not-a-real-provider"}, "Unknown provider"),
			({"base_url": "not-a-url"}, "Base URL"),
		):
			with self.subTest(**overrides), self.assertRaisesRegex(frappe.ValidationError, error):
				frappe.get_doc(_provider(**overrides)).insert()
		with self.subTest("named by its lowercase name"):
			doc = frappe.get_doc(_provider(provider="OpenRouter")).insert()
			self.assertEqual((doc.name, doc.provider), ("openrouter", "openrouter"))
		with self.subTest("a gateway the daemon routes itself"):
			doc = frappe.get_doc(_provider(provider="OrcaRouter", api_key="sk-orca-test")).insert()
			self.assertEqual((doc.name, doc.provider), ("orcarouter", "orcarouter"))


class TestProviderCredentialResolution(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_a_model_takes_what_it_lacks_from_its_enabled_provider(self):
		for label, provider, model, key, expected in (
			("the provider's key", {}, {}, "api_key", "sk-from-provider"),
			("the model's own key first", {}, {"api_key": "sk-on-model"}, "api_key", "sk-on-model"),
			("no key from a disabled provider", {"enabled": 0}, {}, "api_key", None),
			("no key without a provider row", None, {}, "api_key", None),
			(
				"the provider's base URL",
				{"base_url": "http://gateway.local"},
				{},
				"api_base",
				"http://gateway.local",
			),
		):
			with self.subTest(label):
				if provider is not None:
					frappe.get_doc(_provider(api_key="sk-from-provider", **provider)).insert()
				doc = frappe.get_doc(_model(**model)).insert()
				self.assertEqual(model_config(doc.name)[key], expected)
			frappe.db.rollback()

	def test_a_gateway_model_id_resolves_the_provider_named_by_its_first_segment(self):
		# litellm has no adapter for orcarouter; the daemon routes it by the id's prefix
		frappe.get_doc(
			_provider(provider="orcarouter", api_key="sk-orca-test", base_url="https://api.orcarouter.ai/v1")
		).insert()
		doc = frappe.get_doc(_model(title="OrcaRouter Model", model_id="orcarouter/openai/gpt-5.5")).insert()
		config = model_config(doc.name)
		self.assertEqual(config["api_key"], "sk-orca-test")
		self.assertEqual(config["api_base"], "https://api.orcarouter.ai/v1")
