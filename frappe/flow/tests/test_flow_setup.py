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

	def test_a_server_of_ones_own_is_saved_at_its_address(self):
		frappe.db.delete("Flow Provider", {"name": "custom_openai"})
		with patch.object(setup.requests, "get") as get:
			self.assertEqual(
				setup.connect("custom_openai", None, "http://models.example.com/v1/"), {"ok": True}
			)
		self.assertEqual(get.call_args.args[0], "http://models.example.com/v1/models")
		self.assertEqual(
			frappe.db.get_value("Flow Provider", "custom_openai", "base_url"), "http://models.example.com/v1"
		)

	def test_a_server_that_refuses_the_key_or_has_no_address_is_not_saved(self):
		frappe.db.delete("Flow Provider", {"name": "custom_openai"})
		refused = requests.HTTPError(response=SimpleNamespace(status_code=401))
		with patch.object(setup.requests, "get") as get:
			get.return_value.raise_for_status.side_effect = refused
			result = setup.connect("custom_openai", "wrong", "https://models.example.com/v1")
		self.assertEqual(result["reason"], "wrong_key")
		self.assertRaises(frappe.ValidationError, setup.connect, "custom_openai", None, "models.example.com")
		self.assertFalse(frappe.db.exists("Flow Provider", "custom_openai"))

	@patch.object(setup, "_ask_with_key")
	def test_a_provider_is_removed_with_its_models(self, _ask):
		setup.connect("anthropic", "sk-ant-good-key-0000000000000")
		with (
			patch.object(setup, "_check", return_value=None),
			patch("frappe.flow.assistant.ensure_builtin_assistant"),
		):
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


SITE_KEY = {"ai_keys": [{"gateway_url": "https://ai.example.com/", "api_key": "grove-key"}]}
# what Grove lists for the key, each model under its vendor
LISTED = ["morph/glm-5.3-flash", "openai/gpt-6-luna", "openai/text-embedding-3-small"]


class TestSiteKeyProvider(IntegrationTestCase):
	"""A site whose config has a Grove key chats on Flow's first open, without setup."""

	def setUp(self):
		frappe.db.delete("Flow Model", {"provider": "grove"})
		frappe.db.delete("Flow Provider", {"name": "grove"})
		frappe.cache.delete_value(setup.GROVE_DOWN_CACHE)

	def tearDown(self):
		frappe.db.rollback()

	def _sync(self, conf=SITE_KEY, listed=LISTED):
		def gateway(url, headers, timeout):
			self.assertEqual(url, "https://ai.example.com/openai/v1/models")
			response = SimpleNamespace(raise_for_status=lambda: None)
			response.json = lambda: {"data": [{"id": model} for model in listed]}
			return response

		with (
			patch.dict(frappe.conf, conf),
			patch.object(setup.requests, "get", side_effect=gateway) as get,
			patch("frappe.flow.assistant.ensure_builtin_assistant") as assistant,
		):
			setup.sync_site_provider()
		return get, assistant

	def test_the_first_open_adds_grove_with_luna_alone(self):
		_get, assistant = self._sync()
		self.assertTrue(frappe.db.get_value("Flow Provider", "grove", "enabled"))
		self.assertFalse(
			frappe.get_doc("Flow Provider", "grove").get_password("api_key", raise_exception=False)
		)
		models = frappe.get_all("Flow Model", {"provider": "grove"}, ["name", "model_id", "enabled"])
		self.assertEqual(
			[(model.model_id, model.enabled) for model in models], [("grove/openai/gpt-6-luna", 1)]
		)
		# the Assistant chats with it
		assistant.assert_called_once_with(model=models[0].name)

	def test_a_key_without_luna_adds_nothing_so_setup_shows(self):
		self._sync(listed=["morph/glm-5.3-flash", "gpt-6-luna"])
		self.assertFalse(frappe.db.exists("Flow Provider", "grove"))

	def test_later_opens_and_sites_without_a_key_ask_no_gateway(self):
		self._sync()
		get, _assistant = self._sync()
		get.assert_not_called()
		frappe.db.rollback()
		get, _assistant = self._sync({"ai_keys": []})
		get.assert_not_called()
		self.assertFalse(frappe.db.exists("Flow Provider", "grove"))

	def test_a_gateway_that_does_not_answer_adds_nothing_and_is_asked_again_later(self):
		with (
			patch.dict(frappe.conf, SITE_KEY),
			patch.object(setup.requests, "get", side_effect=requests.ConnectionError),
		):
			setup.sync_site_provider()
		self.assertFalse(frappe.db.exists("Flow Provider", "grove"))
		# the next opens don't wait on it again for a while
		get, _assistant = self._sync()
		get.assert_not_called()
		frappe.cache.delete_value(setup.GROVE_DOWN_CACHE)
		self._sync()
		self.assertTrue(frappe.db.exists("Flow Provider", "grove"))

	def test_two_first_opens_at_once_add_grove_once(self):
		self._sync()
		# the other open checked before this one's rows were there
		with patch.object(frappe.db, "exists", return_value=False):
			self._sync()
		self.assertEqual(frappe.db.count("Flow Model", {"provider": "grove"}), 1)

	def test_a_key_that_just_arrived_is_read_from_the_config_file(self):
		# site config is cached for up to a minute: the key is in the file, not yet in frappe.conf
		with patch.object(frappe, "get_site_config", return_value=SITE_KEY):
			self._sync({"ai_keys": []})
		self.assertTrue(frappe.db.exists("Flow Provider", "grove"))
