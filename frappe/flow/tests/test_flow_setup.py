# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from types import SimpleNamespace
from unittest.mock import patch

import requests

import frappe
from frappe.flow.api import setup
from frappe.tests import IntegrationTestCase


class TestFlowSetup(IntegrationTestCase):
	def setUp(self):
		# start as a site that never connected Anthropic, whatever this one has; undone in tearDown
		frappe.db.delete("Flow Model", {"provider": "anthropic"})
		frappe.db.delete("Flow Provider", {"name": "anthropic"})

	def tearDown(self):
		frappe.db.rollback()

	def test_models_are_named_as_people_know_them(self):
		self.assertEqual(setup._title("claude-sonnet-5-5"), "Claude Sonnet 5.5")
		self.assertEqual(setup._title("gpt-5.4-mini"), "GPT-5.4 mini")
		self.assertEqual(setup._title("anthropic/claude-opus-5-5"), "Claude Opus 5.5")
		self.assertEqual(setup._title("llama3.3:70b"), "llama3.3:70b")

	def test_a_refused_key_saves_nothing(self):
		refused = requests.HTTPError(response=SimpleNamespace(status_code=401))
		with patch.object(setup, "_ask_with_key", side_effect=refused):
			result = setup.connect("anthropic", "sk-ant-wrong-key-000000000000")
		self.assertEqual(result["reason"], "wrong_key")
		self.assertFalse(frappe.db.exists("Flow Provider", "anthropic"))

	def test_a_key_is_checked_where_the_service_needs_one(self):
		# Gemini refuses a bad key with 400; OpenRouter's list is public, so its key is asked
		bad = requests.HTTPError(response=SimpleNamespace(status_code=400))
		with patch.object(setup, "_ask_with_key", side_effect=bad):
			self.assertEqual(setup.connect("gemini", "AIza-bad")["reason"], "wrong_key")
		with patch.object(setup, "_ask_with_key", side_effect=bad) as ask:
			setup.connect("openrouter", "sk-or-bad")
		self.assertEqual(ask.call_args.args[0], "https://openrouter.ai/api/v1/key")

	@patch.object(setup, "_ask_with_key")
	def test_a_provider_is_removed_with_its_models(self, _ask):
		setup.connect("anthropic", "sk-ant-good-key-0000000000000")
		with patch.object(setup, "_check", return_value=None):
			setup.add_model("anthropic", "claude-haiku-5-5")
		setup.remove_provider("anthropic")
		self.assertFalse(frappe.db.exists("Flow Provider", "anthropic"))
		self.assertFalse(frappe.db.exists("Flow Model", {"provider": "anthropic"}))

	@patch.object(setup, "_ask_with_key")
	def test_a_working_key_saves_the_provider_and_no_model(self, _listed):
		self.assertEqual(setup.connect("anthropic", "sk-ant-good-key-0000000000000"), {"ok": True})
		provider = frappe.get_doc("Flow Provider", "anthropic")
		self.assertEqual(provider.get_password("api_key"), "sk-ant-good-key-0000000000000")
		self.assertFalse(frappe.db.exists("Flow Model", {"provider": "anthropic"}))

	@patch.object(setup, "_ask_with_key")
	def test_a_model_is_saved_only_once_it_answers(self, _listed):
		setup.connect("anthropic", "sk-ant-good-key-0000000000000")
		refusal = setup._refused("not_offered", "Anthropic has no model called claude-nope.")
		with patch.object(setup, "_check", return_value=refusal):
			self.assertEqual(setup.add_model("anthropic", "claude-nope"), {"check": refusal})
		self.assertFalse(frappe.db.exists("Flow Model", {"provider": "anthropic"}))
		with patch.object(setup, "_check", return_value=None):
			self.assertEqual(setup.add_model("anthropic", "anthropic/claude-sonnet-5-5")["enabled"], 1)

	def test_a_service_says_why_in_its_own_words(self):
		wrapped = Exception(
			'litellm.BadRequestError: OpenrouterException - {"error":{"message":"sdfas is not a valid'
			' model ID","code":400}}'
		)
		self.assertEqual(setup._reason(wrapped), "sdfas is not a valid model ID")
		self.assertEqual(setup._reason(Exception("litellm.APIError: APIError - Overloaded")), "Overloaded")

	@patch.object(setup, "_ask_with_key")
	def test_a_model_that_embeds_is_added_as_an_embedding_model_and_kept_out_of_the_chat(self, _ask):
		from frappe.flow.api.api import boot

		setup.connect("anthropic", "sk-ant-good-key-0000000000000")
		chat_refused = setup._refused("failed", "This is not a chat model.")

		# the first run wants one to chat with: no second try
		with patch.object(setup, "_check", return_value=chat_refused) as check:
			self.assertEqual(setup.add_model("anthropic", "vectors-1", for_chat=1)["check"], chat_refused)
		self.assertEqual(check.call_count, 1)

		# elsewhere, one that doesn't chat but embeds is an embedding model, whatever its name
		with patch.object(
			setup, "_check", side_effect=lambda *a, embedding=False: None if embedding else chat_refused
		):
			added = setup.add_model("anthropic", "vectors-1")
		self.assertTrue(added["embedding"])
		self.assertEqual(frappe.db.get_value("Flow Model", added["name"], "embedding"), 1)
		self.assertNotIn(added["name"], [model.name for model in boot()["models"]])

		# one that does neither isn't added, and says why it didn't chat
		with patch.object(setup, "_check", return_value=chat_refused):
			self.assertEqual(setup.add_model("anthropic", "nothing-1")["check"], chat_refused)
		self.assertFalse(frappe.db.exists("Flow Model", {"model_id": "anthropic/nothing-1"}))

	def test_a_key_that_may_not_list_models_is_kept_for_the_first_model_to_check(self):
		forbidden = requests.HTTPError(response=SimpleNamespace(status_code=403))
		with patch.object(setup, "_ask_with_key", side_effect=forbidden):
			self.assertEqual(setup.connect("anthropic", "sk-ant-restricted-0000000000"), {"ok": True})
