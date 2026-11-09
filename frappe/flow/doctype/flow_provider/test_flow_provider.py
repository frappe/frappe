# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

from typing import Any
from unittest.mock import patch

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


SITE_KEY = {"ai_keys": [{"gateway_url": "https://ai.example.com", "api_key": "grove-key"}]}


class TestSiteKeyCredentials(IntegrationTestCase):
	"""A Grove model is called with the key Frappe Cloud writes into site config."""

	def tearDown(self):
		frappe.db.rollback()

	def _grove_model(self, model: str) -> str:
		if not frappe.db.exists("Flow Provider", "grove"):
			frappe.get_doc(_provider(provider="grove", api_key=None)).insert()
		return frappe.get_doc(_model(title=f"Site {model}", provider="grove", model_id=model)).insert().name

	def test_a_grove_model_takes_the_site_key_and_its_gateway(self):
		name = self._grove_model("gpt-x")
		with patch.dict(frappe.conf, SITE_KEY):
			config = model_config(name)
		self.assertEqual(
			(config["model"], config["api_key"], config["api_base"]),
			("grove/gpt-x", "grove-key", "https://ai.example.com"),
		)

	def test_calls_outside_the_flow_server_reach_the_gateway_api_the_flow_server_picks(self):
		from frappe.flow.lib.model import litellm_route

		gateway = "https://ai.example.com"
		self.assertEqual(
			litellm_route("grove/claude-x", gateway), ("anthropic/claude-x", f"{gateway}/anthropic")
		)
		self.assertEqual(litellm_route("grove/gpt-x", gateway), ("openai/gpt-x", f"{gateway}/openai/v1"))
		self.assertEqual(litellm_route("openai/gpt-x", None), ("openai/gpt-x", None))

	def test_a_grove_model_without_a_site_key_says_so(self):
		name = self._grove_model("gpt-x")
		with (
			patch.dict(frappe.conf, {"ai_keys": []}),
			self.assertRaisesRegex(frappe.ValidationError, "Grove key"),
		):
			model_config(name)

	def test_a_grove_model_stops_when_grove_is_turned_off(self):
		name = self._grove_model("gpt-x")
		frappe.db.set_value("Flow Provider", "grove", "enabled", 0)
		with (
			patch.dict(frappe.conf, SITE_KEY),
			self.assertRaisesRegex(frappe.ValidationError, "Grove is turned off"),
		):
			model_config(name)
