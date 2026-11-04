# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.flow.api import setup
from frappe.tests import IntegrationTestCase


class TestFlowSetup(IntegrationTestCase):
	def setUp(self):
		# start as a site that never connected Anthropic, whatever this one has; undone in tearDown
		frappe.db.delete("Flow Model", {"provider": "anthropic"})
		frappe.db.delete("Flow Provider", {"name": "anthropic"})

	def tearDown(self):
		# checks are cached outside the transaction
		for name in frappe.get_all("Flow Model", {"provider": "anthropic"}, pluck="name"):
			frappe.cache.hdel(setup.MODEL_CHECKS, name)
		frappe.db.rollback()

	def test_models_are_named_as_people_know_them(self):
		self.assertEqual(setup._title("claude-sonnet-5-5"), "Claude Sonnet 5.5")
		self.assertEqual(setup._title("gpt-5.4-mini"), "GPT-5.4 mini")
		self.assertEqual(setup._title("anthropic/claude-opus-5-5"), "Claude Opus 5.5")
		self.assertEqual(setup._title("llama3.3:70b"), "llama3.3:70b")

	def test_the_recommended_models_the_service_lists_come_first(self):
		listed = ["claude-haiku-5-5", "claude-opus-5-5", "claude-instant"]
		self.assertEqual(setup._pick("anthropic", listed), ["claude-opus-5-5", "claude-haiku-5-5"])
		# without the service's list, the recommendations as they are
		self.assertEqual(setup._pick("anthropic", [])[0], "claude-sonnet-5-5")
		# a service with none of ours starts on what it has
		self.assertEqual(setup._pick("ollama_chat", ["qwen3:32b"]), ["qwen3:32b"])

	@patch.object(setup, "_listed_models", return_value=["claude-sonnet-5-5", "claude-haiku-5-5"])
	def test_a_refused_key_saves_nothing(self, _listed):
		refusal = setup._refused("wrong_key", "Anthropic didn't accept this key.")
		with patch.object(setup, "_check", return_value=refusal):
			result = setup.connect("anthropic", "sk-ant-wrong-key-000000000000")
		self.assertEqual(result["reason"], "wrong_key")
		self.assertFalse(frappe.db.exists("Flow Provider", "anthropic"))

	@patch.object(setup, "_listed_models", return_value=["claude-sonnet-5-5", "claude-haiku-5-5"])
	def test_a_working_key_saves_the_provider_and_its_models(self, _listed):
		with patch.object(setup, "_check", return_value=None):
			result = setup.connect("anthropic", "sk-ant-good-key-0000000000000")
		self.assertTrue(result["ok"])
		self.assertEqual(result["models"], ["Claude Sonnet 5.5", "Claude Haiku 5.5"])
		provider = frappe.get_doc("Flow Provider", "anthropic")
		self.assertEqual(provider.get_password("api_key"), "sk-ant-good-key-0000000000000")
		self.assertEqual(
			frappe.db.get_value("Flow Model", "Claude Sonnet 5.5", "model_id"), "anthropic/claude-sonnet-5-5"
		)

		# connecting again keeps the models it saved the first time
		with patch.object(setup, "_check", return_value=None):
			again = setup.connect("anthropic", "sk-ant-new-key-00000000000000")
		self.assertEqual(again["models"], result["models"])
		self.assertEqual(frappe.db.count("Flow Model", {"provider": "anthropic"}), 2)

		# one switched off stays off; with every one off, the recommended ones come back on
		frappe.db.set_value("Flow Model", "Claude Haiku 5.5", "enabled", 0)
		with patch.object(setup, "_check", return_value=None):
			self.assertEqual(
				setup.connect("anthropic", "sk-ant-new-key-00000000000000")["models"], ["Claude Sonnet 5.5"]
			)
		frappe.db.set_value("Flow Model", "Claude Sonnet 5.5", "enabled", 0)
		with patch.object(setup, "_check", return_value=None):
			self.assertEqual(
				setup.connect("anthropic", "sk-ant-new-key-00000000000000")["models"], result["models"]
			)
		self.assertEqual(frappe.db.count("Flow Model", {"provider": "anthropic", "enabled": 1}), 2)

	@patch.object(setup, "_listed_models", return_value=["claude-sonnet-5-5"])
	def test_a_model_that_doesnt_answer_is_switched_off_and_says_why(self, _listed):
		with patch.object(setup, "_check", return_value=None):
			setup.connect("anthropic", "sk-ant-good-key-0000000000000")
		refusal = setup._refused("not_offered", "Anthropic doesn't offer this model to your key.")
		with patch.object(setup, "_check", return_value=refusal):
			added = setup.add_model("anthropic", "claude-opus-5-5")
		self.assertEqual((added["enabled"], added["check"]["reason"]), (0, "not_offered"))
		anthropic = next(s for s in setup.services()["services"] if s["name"] == "anthropic")
		listed = anthropic["models"]
		self.assertEqual(
			next(m for m in listed if m.name == "Claude Opus 5.5").check["reason"], "not_offered"
		)

		# a check that passes clears it; one that couldn't reach the service leaves the switch alone
		with patch.object(setup, "_check", return_value=None):
			self.assertTrue(setup.check_model("Claude Sonnet 5.5")["ok"])
		unreachable = setup._refused("unreachable", "Couldn't reach Anthropic from this server.")
		with patch.object(setup, "_check", return_value=unreachable):
			setup.check_model("Claude Sonnet 5.5")
		self.assertEqual(frappe.db.get_value("Flow Model", "Claude Sonnet 5.5", "enabled"), 1)
