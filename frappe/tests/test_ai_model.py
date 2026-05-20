# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from types import SimpleNamespace
from unittest.mock import patch

from frappe.ai.model import ChatResponse, Model, ToolCall
from frappe.tests import UnitTestCase


def _fake_response(content=None, tool_calls=None, finish_reason="stop", usage=None):
	usage = usage or {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}
	message = SimpleNamespace(content=content, tool_calls=tool_calls)
	choice = SimpleNamespace(message=message, finish_reason=finish_reason)
	return SimpleNamespace(choices=[choice], usage=SimpleNamespace(**usage))


class TestModel(UnitTestCase):
	def test_init_requires_model_id(self):
		with self.assertRaises(ValueError):
			Model(model_id="", api_key="x")

	def test_init_allows_empty_api_key_for_local_providers(self):
		m = Model(model_id="ollama/llama3.1", base_url="http://localhost:11434")
		self.assertEqual(m._api_key, "")

	def test_init_rejects_name_with_kwargs(self):
		with self.assertRaises(ValueError):
			Model("Some Model", model_id="openai/gpt-4.1")

	@patch("frappe.get_doc")
	def test_init_from_doc_name(self, mock_get_doc):
		mock_doc = SimpleNamespace(
			enabled=1,
			model_id="anthropic/claude-sonnet-4-6",
			base_url=None,
			params='{"temperature": 0.3}',
			get_password=lambda field, raise_exception=False: "sk-stored",
		)
		mock_get_doc.return_value = mock_doc

		m = Model("Claude Sonnet 4.6")

		mock_get_doc.assert_called_once_with("AI Model", "Claude Sonnet 4.6")
		self.assertEqual(m.model_id, "anthropic/claude-sonnet-4-6")
		self.assertEqual(m._api_key, "sk-stored")
		self.assertEqual(m.params, {"temperature": 0.3})

	@patch("frappe.get_doc")
	def test_init_rejects_disabled_doc(self, mock_get_doc):
		mock_get_doc.return_value = SimpleNamespace(
			enabled=0,
			model_id="anthropic/claude-sonnet-4-6",
			base_url=None,
			params=None,
			get_password=lambda field, raise_exception=False: "sk-stored",
		)
		with self.assertRaises(ValueError):
			Model("Disabled Model")

	@patch("litellm.completion")
	def test_chat_accepts_string_message(self, mock_completion):
		mock_completion.return_value = _fake_response(content="hi there")

		m = Model(model_id="openai/gpt-4.1", api_key="sk-test")
		m.chat("hi")

		messages = mock_completion.call_args.kwargs["messages"]
		self.assertEqual(messages, [{"role": "user", "content": "hi"}])

	@patch("litellm.completion")
	def test_chat_normalizes_text_response(self, mock_completion):
		mock_completion.return_value = _fake_response(content="hi there")

		m = Model(model_id="openai/gpt-4.1", api_key="sk-test")
		resp = m.chat([{"role": "user", "content": "hi"}])

		self.assertIsInstance(resp, ChatResponse)
		self.assertEqual(resp.content, "hi there")
		self.assertEqual(resp.tool_calls, [])
		self.assertEqual(resp.finish_reason, "stop")
		self.assertEqual(resp.usage["total_tokens"], 8)

	@patch("litellm.completion")
	def test_chat_parses_tool_calls(self, mock_completion):
		raw_call = SimpleNamespace(
			id="call_abc",
			function=SimpleNamespace(name="get_weather", arguments='{"city": "Mumbai"}'),
		)
		mock_completion.return_value = _fake_response(
			content=None, tool_calls=[raw_call], finish_reason="tool_calls"
		)

		m = Model(model_id="openai/gpt-4.1", api_key="sk-test")
		resp = m.chat([{"role": "user", "content": "weather?"}])

		self.assertEqual(len(resp.tool_calls), 1)
		call = resp.tool_calls[0]
		self.assertIsInstance(call, ToolCall)
		self.assertEqual(call.id, "call_abc")
		self.assertEqual(call.name, "get_weather")
		self.assertEqual(call.arguments, {"city": "Mumbai"})
		self.assertEqual(resp.finish_reason, "tool_calls")

	@patch("litellm.completion")
	def test_chat_rejects_invalid_tool_arguments(self, mock_completion):
		raw_call = SimpleNamespace(
			id="call_bad",
			function=SimpleNamespace(name="broken", arguments="{not json"),
		)
		mock_completion.return_value = _fake_response(tool_calls=[raw_call])

		m = Model(model_id="openai/gpt-4.1", api_key="sk-test")
		with self.assertRaises(ValueError):
			m.chat([{"role": "user", "content": "hi"}])

	@patch("litellm.completion")
	def test_chat_forwards_params_tools_and_base_url(self, mock_completion):
		mock_completion.return_value = _fake_response(content="ok")

		tools = [{"type": "function", "function": {"name": "ping", "parameters": {}}}]
		m = Model(
			model_id="anthropic/claude-sonnet-4-6",
			api_key="sk-test",
			base_url="http://localhost:11434",
			params={"temperature": 0.2, "max_tokens": 100},
		)
		m.chat([{"role": "user", "content": "hi"}], tools=tools)

		kwargs = mock_completion.call_args.kwargs
		self.assertEqual(kwargs["model"], "anthropic/claude-sonnet-4-6")
		self.assertEqual(kwargs["api_key"], "sk-test")
		self.assertEqual(kwargs["api_base"], "http://localhost:11434")
		self.assertEqual(kwargs["temperature"], 0.2)
		self.assertEqual(kwargs["max_tokens"], 100)
		self.assertEqual(kwargs["tools"], tools)
		self.assertEqual(kwargs["timeout"], 60)
