# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

from typing import Any
from unittest.mock import Mock, patch

import litellm
import requests

import frappe
from frappe.flow.doctype.flow_model.flow_model import _detect_context_window, get_provider_models
from frappe.tests import IntegrationTestCase


def _model(**overrides: Any) -> dict:
	doc = {
		"doctype": "Flow Model",
		"title": "Test Model",
		"model_id": "openai/gpt-4o-mini",
		"enabled": 1,
	}
	doc.update(overrides)
	return doc


class TestFlowModelValidation(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_a_valid_model_is_saved_trimmed(self):
		doc = frappe.get_doc(
			_model(
				title="  Padded  ", model_id="  openai/gpt-4o-mini  ", base_url="  https://api.example.com  "
			)
		).insert()
		self.assertEqual(
			(doc.title, doc.model_id, doc.base_url),
			("Padded", "openai/gpt-4o-mini", "https://api.example.com"),
		)
		for i, (model_id, base_url) in enumerate(
			(
				("openrouter/~anthropic/claude-sonnet-latest", None),
				("openai/gpt-4o-mini", "http://localhost:11434"),
			)
		):
			doc = frappe.get_doc(_model(title=f"Valid {i}", model_id=model_id, base_url=base_url)).insert()
			with self.subTest(model_id=model_id, base_url=base_url):
				self.assertEqual((doc.model_id, doc.base_url), (model_id, base_url))

	def test_invalid_settings_are_refused(self):
		# Format validation runs first and rejects these before reaching the provider check.
		cases = [
			({"model_id": bad}, "Model ID")
			for bad in ("missing-slash", "Uppercase/model", "openai/", "/no-provider", "openai/~")
		]
		cases += [
			({"base_url": bad}, "Base URL")
			for bad in ("ftp://example.com", "not-a-url", "example.com", "//example.com")
		]
		cases += [({"extra_params": bad}, "Extra Params") for bad in ("{not json", "[1, 2]")]
		cases.append(({"model_id": "not_a_real_provider/some-model"}, ""))  # LiteLLM's own message
		for overrides, error in cases:
			with self.subTest(**overrides), self.assertRaisesRegex(frappe.ValidationError, error):
				frappe.get_doc(_model(**overrides)).insert()

	def test_extra_params_go_with_every_call_and_clear_to_empty(self):
		doc = frappe.get_doc(_model(extra_params='{"provider": {"zdr": true}}')).insert()
		self.assertEqual(doc.model_params(), {"provider": {"zdr": True}})
		with patch("litellm.completion") as completion:
			doc.test_connection()
		self.assertEqual(completion.call_args.kwargs["provider"], {"zdr": True})

		doc.extra_params = ""  # what Desk sends for an emptied editor
		doc.save()
		self.assertIsNone(frappe.db.get_value("Flow Model", doc.name, "extra_params"))


class TestFlowModelProvider(IntegrationTestCase):
	def setUp(self):
		if not frappe.db.exists("Flow Provider", "anthropic"):
			frappe.get_doc({"doctype": "Flow Provider", "provider": "anthropic"}).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_a_linked_provider_prefixes_the_model_id_once(self):
		for i, model_id in enumerate(("claude-sonnet-4-6", "anthropic/claude-sonnet-4-6")):
			with self.subTest(model_id=model_id):
				doc = frappe.get_doc(
					_model(title=f"Linked {i}", provider="anthropic", model_id=model_id)
				).insert()
				self.assertEqual(doc.model_id, "anthropic/claude-sonnet-4-6")
				doc.save()
				self.assertEqual(doc.model_id, "anthropic/claude-sonnet-4-6")


class TestContextWindow(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_detect_reads_litellms_max_input_tokens(self):
		catalog = {
			"anthropic/claude-x": {"max_input_tokens": 200000},
			"vendor/x": {},
			"custom_openai/openai/gpt-x": {},  # LiteLLM's window-less stub for a gateway id
			"openai/gpt-x": {"max_input_tokens": 400000},
		}
		for model_id, window in (
			("anthropic/claude-x", 200000),
			("vendor/unknown", 0),
			("vendor/x", 0),
			("custom_openai/openai/gpt-x", 400000),
		):
			with (
				self.subTest(model_id=model_id),
				patch("litellm.get_model_info", side_effect=catalog.__getitem__),
			):
				self.assertEqual(_detect_context_window(model_id), window)

	def test_the_window_follows_the_model_id_and_keeps_the_last_one_found(self):
		with patch("litellm.get_model_info", return_value={"max_input_tokens": 128000}):
			doc = frappe.get_doc(_model()).insert()
		self.assertEqual(doc.context_window, 128000)

		# a valid provider litellm cannot map keeps the prior value
		with patch("litellm.get_model_info", side_effect=Exception("not mapped")):
			doc.model_id = "anthropic/made-up-model-xyz"
			doc.save()
		self.assertEqual(doc.context_window, 128000)

		with patch("litellm.get_model_info", return_value={"max_input_tokens": 1000000}):
			doc.model_id = "anthropic/claude-x"
			doc.save()
		self.assertEqual(doc.context_window, 1000000)


class TestProviderModels(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_a_providers_models_are_asked_live_and_saved_with_its_prefix(self):
		frappe.get_doc({"doctype": "Flow Provider", "provider": "groq", "api_key": "test-key"}).insert()
		frappe.get_doc(
			{
				"doctype": "Flow Provider",
				"provider": "litellm_proxy",
				"base_url": "https://gw.example.com/v1/",
			}
		).insert()
		for provider in ("anthropic", "gemini"):
			if not frappe.db.exists("Flow Provider", provider):
				frappe.get_doc({"doctype": "Flow Provider", "provider": provider}).insert()

		body = {"data": [{"id": "llama-3.3-70b"}, {"id": "groq/compound"}, {"object": "list"}]}
		with self.subTest("groq"), patch("requests.get", return_value=_response(body)) as get:
			# Groq's own groq/compound still gets the prefix: litellm strips one
			self.assertEqual(get_provider_models("groq"), ["groq/groq/compound", "groq/llama-3.3-70b"])
			self.assertEqual(get.call_args.args[0], "https://api.groq.com/openai/v1/models")
			self.assertEqual(get.call_args.kwargs["headers"], {"Authorization": "Bearer test-key"})

		body = {"data": [{"id": "openai/gpt-6-sol"}]}
		with self.subTest("a base URL"), patch("requests.get", return_value=_response(body)) as get:
			self.assertEqual(get_provider_models("litellm_proxy"), ["litellm_proxy/openai/gpt-6-sol"])
			self.assertEqual(get.call_args.args[0], "https://gw.example.com/v1/models")

		for provider, body, models, params in (
			("anthropic", {"data": [{"id": "claude-x"}]}, ["anthropic/claude-x"], {"limit": 1000}),
			("gemini", {"models": [{"name": "models/gemini-x"}]}, ["gemini/gemini-x"], {"pageSize": 1000}),
		):
			with self.subTest(provider), patch("requests.get", return_value=_response(body)) as get:
				self.assertEqual(get_provider_models(provider), models)  # every model on one page
				self.assertEqual(get.call_args.kwargs["params"], params)

		with (
			self.subTest("LiteLLM's catalog when the provider does not answer"),
			patch("requests.get", side_effect=requests.ConnectionError("down")),
			patch.dict(litellm.models_by_provider, {"groq": {"llama-3.3-70b", "groq/llama-guard"}}),
		):
			# the catalog's own prefix is not doubled
			self.assertEqual(get_provider_models("groq"), ["groq/llama-3.3-70b", "groq/llama-guard"])

		frappe.set_user("Guest")
		with self.subTest("nothing for users who cannot edit models"), patch("requests.get") as get:
			self.assertEqual(get_provider_models("groq"), [])
			get.assert_not_called()


def _response(body: dict) -> Mock:
	response = Mock()
	response.json.return_value = body
	return response
