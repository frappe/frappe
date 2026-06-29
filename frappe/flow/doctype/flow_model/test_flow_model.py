# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

from typing import Any
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from flow.flow.doctype.flow_model.flow_model import _detect_context_window


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

	def test_valid_model_inserts(self):
		doc = frappe.get_doc(_model()).insert()

		self.assertEqual(doc.model_id, "openai/gpt-4o-mini")
		self.assertTrue(doc.enabled)

	def test_normalize_strips_whitespace(self):
		doc = frappe.get_doc(
			_model(
				title="  Padded  ", model_id="  openai/gpt-4o-mini  ", base_url="  https://api.example.com  "
			)
		).insert()

		self.assertEqual(doc.title, "Padded")
		self.assertEqual(doc.model_id, "openai/gpt-4o-mini")
		self.assertEqual(doc.base_url, "https://api.example.com")

	def test_invalid_model_id_format_rejected(self):
		# Format validation runs first and rejects these before reaching the provider check.
		for bad in ("missing-slash", "Uppercase/model", "openai/", "/no-provider"):
			with self.subTest(model_id=bad):
				doc = frappe.get_doc(_model(model_id=bad))
				with self.assertRaisesRegex(frappe.ValidationError, "Model ID"):
					doc.insert()

	def test_unknown_provider_rejected(self):
		doc = frappe.get_doc(_model(model_id="not_a_real_provider/some-model"))

		with self.assertRaises(frappe.ValidationError):
			doc.insert()


class TestFlowModelProvider(IntegrationTestCase):
	def setUp(self):
		if not frappe.db.exists("Flow Provider", "anthropic"):
			frappe.get_doc({"doctype": "Flow Provider", "provider": "anthropic"}).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_linked_provider_composes_model_id(self):
		doc = frappe.get_doc(_model(provider="anthropic", model_id="claude-sonnet-4-6")).insert()

		self.assertEqual(doc.model_id, "anthropic/claude-sonnet-4-6")

	def test_compose_is_idempotent_for_prefixed_model_id(self):
		doc = frappe.get_doc(_model(provider="anthropic", model_id="anthropic/claude-sonnet-4-6")).insert()

		self.assertEqual(doc.model_id, "anthropic/claude-sonnet-4-6")

	def test_resave_does_not_double_prefix(self):
		doc = frappe.get_doc(_model(provider="anthropic", model_id="claude-sonnet-4-6")).insert()
		doc.save()

		self.assertEqual(doc.model_id, "anthropic/claude-sonnet-4-6")

	def test_full_model_id_without_provider_still_works(self):
		doc = frappe.get_doc(_model(model_id="openai/gpt-4o-mini")).insert()

		self.assertFalse(doc.provider)
		self.assertEqual(doc.model_id, "openai/gpt-4o-mini")


class TestFlowModelBaseURL(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_https_base_url_accepted(self):
		doc = frappe.get_doc(_model(base_url="https://api.example.com/v1")).insert()

		self.assertEqual(doc.base_url, "https://api.example.com/v1")

	def test_http_base_url_accepted(self):
		doc = frappe.get_doc(_model(base_url="http://localhost:11434")).insert()

		self.assertEqual(doc.base_url, "http://localhost:11434")

	def test_non_http_base_url_rejected(self):
		for bad in ("ftp://example.com", "not-a-url", "example.com", "//example.com"):
			with self.subTest(base_url=bad):
				doc = frappe.get_doc(_model(base_url=bad))
				with self.assertRaisesRegex(frappe.ValidationError, "Base URL"):
					doc.insert()


class TestFlowModelParams(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_valid_params_json_accepted(self):
		doc = frappe.get_doc(_model(params='{"temperature": 0.2, "max_tokens": 500}')).insert()

		import json

		self.assertEqual(json.loads(doc.params), {"temperature": 0.2, "max_tokens": 500})

	def test_invalid_json_rejected(self):
		doc = frappe.get_doc(_model(params="{not json"))

		with self.assertRaisesRegex(frappe.ValidationError, "Params"):
			doc.insert()

	def test_non_object_json_rejected(self):
		doc = frappe.get_doc(_model(params="[1, 2, 3]"))

		with self.assertRaisesRegex(frappe.ValidationError, "Params"):
			doc.insert()

	def test_reserved_params_rejected(self):
		for reserved in ("model", "api_key", "messages", "stream", "tools"):
			with self.subTest(key=reserved):
				doc = frappe.get_doc(_model(params=f'{{"{reserved}": "x"}}'))
				with self.assertRaisesRegex(frappe.ValidationError, "reserved keys"):
					doc.insert()


class TestContextWindow(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_detect_returns_max_input_tokens(self):
		with patch("litellm.get_model_info", return_value={"max_input_tokens": 200000}):
			self.assertEqual(_detect_context_window("anthropic/claude-x"), 200000)

	def test_detect_unmapped_model_returns_zero(self):
		with patch("litellm.get_model_info", side_effect=Exception("not mapped")):
			self.assertEqual(_detect_context_window("vendor/unknown"), 0)

	def test_detect_missing_field_returns_zero(self):
		with patch("litellm.get_model_info", return_value={}):
			self.assertEqual(_detect_context_window("vendor/x"), 0)

	def test_auto_fills_on_insert(self):
		with patch("litellm.get_model_info", return_value={"max_input_tokens": 128000}):
			doc = frappe.get_doc(_model()).insert()
		self.assertEqual(doc.context_window, 128000)

	def test_redetects_on_model_id_change(self):
		with patch("litellm.get_model_info", return_value={"max_input_tokens": 128000}):
			doc = frappe.get_doc(_model()).insert()
		# New model id (valid provider) -> re-detect, overriding the prior value.
		with patch("litellm.get_model_info", return_value={"max_input_tokens": 1000000}) as m:
			doc.model_id = "anthropic/claude-x"
			doc.save()
		m.assert_called()
		self.assertEqual(doc.context_window, 1000000)

	def test_keeps_existing_when_new_model_unmapped(self):
		with patch("litellm.get_model_info", return_value={"max_input_tokens": 128000}):
			doc = frappe.get_doc(_model()).insert()
		# Valid provider, but litellm can't map the model -> keep the prior detected value.
		with patch("litellm.get_model_info", side_effect=Exception("not mapped")):
			doc.model_id = "anthropic/made-up-model-xyz"
			doc.save()
		self.assertEqual(doc.context_window, 128000)
