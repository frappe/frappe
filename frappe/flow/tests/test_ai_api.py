# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
from typing import Any
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from werkzeug.wrappers import Response

from flow.api import attach_file, recover_session, resume_run, start_run, submit_feedback
from flow.api.api import _parse_attachments
from flow.lib.model import ChatResponse, Model, ToolCall
from flow.memory import store as memory_store
from flow.tools.builtins import sync_builtin_tools


def _scripted_stream(text_parts: list[str], response: ChatResponse):
	for part in text_parts:
		if part:
			yield part
	return response


def _stream_chat(text_parts: list[str], response: ChatResponse):
	"""Build a side_effect function that returns a stream when stream=True, else the response."""

	def chat(self, messages, tools=None, *, stream=False):
		if stream:
			return _scripted_stream(text_parts, response)
		return response

	return chat


def _sse_events(response: Response) -> list[dict[str, Any]]:
	"""Parse an SSE response body into a list of event dicts."""
	body = b"".join(response.iter_encoded()).decode()
	events = []
	for block in body.split("\n\n"):
		block = block.strip()
		if not block:
			continue
		data_lines = [line[6:] for line in block.split("\n") if line.startswith("data: ")]
		if data_lines:
			events.append(json.loads("\n".join(data_lines)))
	return events


def _model_doc(**overrides: Any) -> dict:
	doc = {
		"doctype": "Flow Model",
		"title": "Test API Model",
		"model_id": "openai/gpt-4o-mini",
		"enabled": 1,
	}
	doc.update(overrides)
	return doc


def _agent_doc(model_name: str, **overrides: Any) -> dict:
	doc = {
		"doctype": "Flow Agent",
		"title": "Test API Agent",
		"model": model_name,
		"instructions": "Be terse.",
		"enabled": 1,
	}
	doc.update(overrides)
	return doc


def _final(text: str = "done") -> ChatResponse:
	return ChatResponse(
		content=text,
		finish_reason="stop",
		usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
	)


def _confirm_call(call_id: str = "c1") -> ChatResponse:
	"""A response that calls the `execute` tool, which requires confirmation and so pauses the run."""
	return ChatResponse(
		content=None,
		tool_calls=[ToolCall(id=call_id, name="execute", arguments={"code": "result = 1"})],
		finish_reason="tool_calls",
		usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
	)


def _memory_call(content: str = "Widget A maps to WGT-001.", call_id: str = "m1") -> ChatResponse:
	"""A response that calls update_memory (runs inline, no confirmation)."""
	return ChatResponse(
		content=None,
		tool_calls=[
			ToolCall(id=call_id, name="update_memory", arguments={"content": content, "scope": "agent"})
		],
		finish_reason="tool_calls",
		usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
	)


class TestStartRun(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sync_builtin_tools()

	def setUp(self):
		self.model = frappe.get_doc(_model_doc()).insert()
		self.agent = frappe.get_doc(_agent_doc(self.model.name)).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_start_run_without_agent_uses_default_assistant(self):
		from flow.assistant import ASSISTANT_AGENT_TITLE

		with patch.object(Model, "chat", return_value=_final("hello")):
			payload = start_run("hi")

		self.assertEqual(payload["status"], "Completed")
		self.assertEqual(payload["output"], "hello")
		session = frappe.get_doc("Flow Session", payload["session"])
		self.assertEqual(session.agent, ASSISTANT_AGENT_TITLE)

	def test_start_run_with_named_agent_links_to_agent(self):
		with patch.object(Model, "chat", return_value=_final()):
			payload = start_run("hi", agent=self.agent.name)

		session = frappe.get_doc("Flow Session", payload["session"])
		self.assertEqual(session.agent, self.agent.name)
		self.assertEqual(payload["status"], "Completed")

	def test_start_run_paused_returns_questions(self):
		with patch.object(Model, "chat", return_value=_confirm_call()):
			payload = start_run("delete the records", agent=self.agent.name)

		self.assertEqual(payload["status"], "Paused")
		self.assertEqual(len(payload["questions"]), 1)
		self.assertEqual(payload["questions"][0]["options"], ["Approve", "Deny"])
		self.assertEqual(payload["questions"][0]["key"], "c1")

	def test_start_run_rejects_empty_input(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Input"):
			start_run("")

	def test_start_run_rejects_whitespace_input(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Input"):
			start_run("   ")

	def test_start_run_unknown_agent_raises(self):
		with self.assertRaises(frappe.DoesNotExistError):
			start_run("hi", agent="does-not-exist")

	def test_start_run_stream_returns_sse_response_with_event_sequence(self):
		with patch.object(Model, "chat", new=_stream_chat(["hello ", "world"], _final("hello world"))):
			response = start_run("hi", agent=self.agent.name, stream=True)
			self.assertIsInstance(response, Response)
			self.assertEqual(response.mimetype, "text/event-stream")
			events = _sse_events(response)

		types = [e["type"] for e in events]
		self.assertEqual(types[0], "run_started")
		self.assertEqual(types[-1], "done")
		text_deltas = [e["delta"] for e in events if e["type"] == "text"]
		self.assertEqual(text_deltas, ["hello ", "world"])

		done = events[-1]
		self.assertEqual(done["status"], "Completed")
		self.assertEqual(done["output"], "hello world")

		run = frappe.get_doc("Flow Run", events[0]["name"])
		self.assertEqual(run.status, "Completed")
		self.assertEqual(run.output, "hello world")

	def test_start_run_stream_without_agent_uses_default_assistant(self):
		from flow.assistant import ASSISTANT_AGENT_TITLE

		with patch.object(Model, "chat", new=_stream_chat(["hi"], _final("hi"))):
			response = start_run("hello", stream=True)
			events = _sse_events(response)

		self.assertEqual(events[0]["type"], "run_started")
		run = frappe.get_doc("Flow Run", events[0]["name"])
		session = frappe.get_doc("Flow Session", run.session)
		self.assertEqual(session.agent, ASSISTANT_AGENT_TITLE)

	def test_start_run_stream_accepts_truthy_string(self):
		with patch.object(Model, "chat", new=_stream_chat(["ok"], _final("ok"))):
			response = start_run("hi", agent=self.agent.name, stream="true")
			self.assertIsInstance(response, Response)
			_sse_events(response)  # drain inside patch

	def test_start_run_stream_failure_emits_error_event(self):
		def boom(self, messages, tools=None, *, stream=False):
			raise RuntimeError("kaboom")

		with patch.object(Model, "chat", new=boom):
			response = start_run("hi", agent=self.agent.name, stream=True)
			events = _sse_events(response)

		self.assertEqual(events[0]["type"], "run_started")
		self.assertEqual(events[-1]["type"], "error")
		self.assertIn("kaboom", events[-1]["message"])

		run = frappe.get_doc("Flow Run", events[0]["name"])
		self.assertEqual(run.status, "Failed")


class TestResumeRun(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sync_builtin_tools()

	def setUp(self):
		self.model = frappe.get_doc(_model_doc()).insert()
		self.agent = frappe.get_doc(_agent_doc(self.model.name)).insert()

	def tearDown(self):
		frappe.db.rollback()

	def _pause(self, agent: str | None = None) -> str:
		with patch.object(Model, "chat", return_value=_confirm_call()):
			payload = start_run("do it", agent=agent)
		self.assertEqual(payload["status"], "Paused")
		return payload["name"]

	def test_resume_paused_named_agent_completes(self):
		run_name = self._pause(agent=self.agent.name)

		with patch.object(Model, "chat", return_value=_final("ok")):
			payload = resume_run(run_name, {"c1": "use a different approach"})

		self.assertEqual(payload["status"], "Completed")
		self.assertEqual(payload["output"], "ok")

	def test_resume_paused_assistant_completes(self):
		run_name = self._pause(agent=None)

		with patch.object(Model, "chat", return_value=_final("ok")):
			payload = resume_run(run_name, {"c1": "use a different approach"})

		self.assertEqual(payload["status"], "Completed")

	def test_resume_deny_stops_run_without_calling_model(self):
		run_name = self._pause(agent=self.agent.name)

		called: list[bool] = []

		def chat(self, messages, tools=None, *, stream=False):
			called.append(True)
			return _final("should not happen")

		with patch.object(Model, "chat", new=chat):
			payload = resume_run(run_name, {"c1": "Deny"})

		self.assertEqual(payload["status"], "Completed")
		self.assertEqual(called, [])  # model never called after Deny
		self.assertEqual(frappe.get_doc("Flow Run", run_name).status, "Completed")

	def test_resume_accepts_json_string_answers(self):
		run_name = self._pause(agent=self.agent.name)

		with patch.object(Model, "chat", return_value=_final("ok")):
			payload = resume_run(run_name, json.dumps({"c1": "use a different approach"}))

		self.assertEqual(payload["status"], "Completed")

	def test_resume_can_pause_again_with_new_questions(self):
		run_name = self._pause(agent=self.agent.name)

		with patch.object(Model, "chat", return_value=_confirm_call(call_id="c2")):
			payload = resume_run(run_name, {"c1": "use a different approach"})

		self.assertEqual(payload["status"], "Paused")
		self.assertEqual(payload["questions"][0]["key"], "c2")

	def test_resume_rejects_non_paused_run(self):
		with patch.object(Model, "chat", return_value=_final()):
			payload = start_run("hi", agent=self.agent.name)

		with self.assertRaisesRegex(frappe.ValidationError, "Paused"):
			resume_run(payload["name"], {})

	def test_resume_rejects_unknown_run(self):
		with self.assertRaises(frappe.DoesNotExistError):
			resume_run("does-not-exist", {})

	def test_resume_rejects_invalid_answers_type(self):
		run_name = self._pause(agent=self.agent.name)

		with self.assertRaisesRegex(frappe.ValidationError, "JSON object"):
			resume_run(run_name, "not json")

	def test_resume_stream_returns_sse_response(self):
		# pause first via non-streaming start
		with patch.object(Model, "chat", return_value=_confirm_call()):
			payload = start_run("do it", agent=self.agent.name)
		run_name = payload["name"]

		with patch.object(Model, "chat", new=_stream_chat(["ok"], _final("ok"))):
			response = resume_run(run_name, {"c1": "use a different approach"}, stream=True)
			self.assertIsInstance(response, Response)
			events = _sse_events(response)

		types = [e["type"] for e in events]
		self.assertIn("run_started", types)
		self.assertIn("done", types)
		self.assertEqual(events[-1]["status"], "Completed")

		run = frappe.get_doc("Flow Run", run_name)
		self.assertEqual(run.status, "Completed")

	def test_resume_failure_marks_run_failed(self):
		run_name = self._pause(agent=self.agent.name)

		with patch.object(Model, "chat", side_effect=RuntimeError("boom")):
			with self.assertRaises(RuntimeError):
				resume_run(run_name, {"c1": "use a different approach"})

		failed = frappe.get_doc("Flow Run", run_name)
		self.assertEqual(failed.status, "Failed")
		self.assertIn("boom", failed.error)


class TestStartRunSessions(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sync_builtin_tools()

	def setUp(self):
		self.model_doc = frappe.get_doc(
			{
				"doctype": "Flow Model",
				"title": "Test Session Model",
				"model_id": "openai/gpt-4o-mini",
				"enabled": 1,
			}
		).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_start_run_without_session_creates_new_session(self):
		with patch.object(Model, "chat", return_value=_final()):
			result = start_run("hello world")

		self.assertIsNotNone(result["session"])
		session = frappe.get_doc("Flow Session", result["session"])
		self.assertEqual(session.owner, frappe.session.user)
		self.assertEqual(session.title, "hello world")

	def test_start_run_links_run_to_session(self):
		with patch.object(Model, "chat", return_value=_final()):
			result = start_run("hi")

		run = frappe.get_doc("Flow Run", result["name"])
		self.assertEqual(run.session, result["session"])

	def test_second_turn_threads_prior_messages(self):
		captured: list[list[dict[str, Any]]] = []

		def capture_chat(messages: list[dict[str, Any]], **_: Any) -> ChatResponse:
			captured.append([dict(m) for m in messages])
			return _final(f"reply {len(captured)}")

		with patch.object(Model, "chat", side_effect=capture_chat):
			first = start_run("what is 2+2")
			start_run("and what about 3+3", session=first["session"])

		second_messages = captured[1]
		user_msgs = [m for m in second_messages if m.get("role") == "user"]
		self.assertEqual([m["content"] for m in user_msgs], ["what is 2+2", "and what about 3+3"])
		assistant_msgs = [m for m in second_messages if m.get("role") == "assistant"]
		self.assertTrue(any(m.get("content") == "reply 1" for m in assistant_msgs))

	def test_explicit_session_id_reuses_it(self):
		from flow.assistant import sync_builtin_assistant
		from flow.assistant.assistant import ASSISTANT_AGENT_TITLE

		sync_builtin_assistant(model=self.model_doc.name)
		session = frappe.get_doc(
			{"doctype": "Flow Session", "agent": ASSISTANT_AGENT_TITLE, "title": "carried"}
		).insert(ignore_permissions=True)

		with patch.object(Model, "chat", return_value=_final()):
			result = start_run("hi", session=session.name)

		self.assertEqual(result["session"], session.name)

	def test_unknown_session_raises(self):
		with self.assertRaises(frappe.DoesNotExistError):
			start_run("hi", session="ghost-session-id")

	def test_agent_mismatch_with_session_raises(self):
		agent_a = frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Agent Mismatch A",
				"model": self.model_doc.name,
				"instructions": "x",
				"enabled": 1,
			}
		).insert()
		agent_b = frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Agent Mismatch B",
				"model": self.model_doc.name,
				"instructions": "x",
				"enabled": 1,
			}
		).insert()
		session = frappe.get_doc({"doctype": "Flow Session", "agent": agent_a.name}).insert(
			ignore_permissions=True
		)

		with self.assertRaisesRegex(frappe.ValidationError, "Agent Mismatch"):
			start_run("hi", session=session.name, agent=agent_b.name)

	def test_paused_session_blocks_new_turn(self):
		with patch.object(Model, "chat", return_value=_confirm_call()):
			first = start_run("delete everything")

		self.assertEqual(first["status"], "Paused")

		with patch.object(Model, "chat", return_value=_final()):
			with self.assertRaisesRegex(frappe.ValidationError, "paused"):
				start_run("nevermind", session=first["session"])


class TestStartRunSecurity(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sync_builtin_tools()

	def setUp(self):
		self.model_doc = frappe.get_doc(
			{
				"doctype": "Flow Model",
				"title": "Test Security Model",
				"model_id": "openai/gpt-4o-mini",
				"enabled": 1,
			}
		).insert()
		self.other_user = _ensure_user("other-ai-user@example.com")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_session_owned_by_other_user_is_rejected(self):
		frappe.set_user(self.other_user)
		with patch.object(Model, "chat", return_value=_final()):
			theirs = start_run("private chat")
		frappe.set_user("Administrator")

		frappe.set_user(_ensure_user("third-ai-user@example.com"))
		with self.assertRaises(frappe.PermissionError):
			start_run("steal context", session=theirs["session"])


class TestStartRunAttachments(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sync_builtin_tools()

	def setUp(self):
		self.model = frappe.get_doc(_model_doc(title="Attach Model")).insert()
		self.agent = frappe.get_doc(_agent_doc(self.model.name, title="Attach Agent")).insert()

	def tearDown(self):
		frappe.db.rollback()

	def _file(self, file_name: str = "notes.txt", content: str = "the secret code is 1234"):
		return frappe.get_doc(
			{"doctype": "File", "file_name": file_name, "content": content, "is_private": 1}
		).insert()

	def _capture(self):
		captured: list[list[dict[str, Any]]] = []

		def chat(messages: list[dict[str, Any]], **_: Any) -> ChatResponse:
			captured.append([dict(m) for m in messages])
			return _final(f"reply {len(captured)}")

		return captured, chat

	def test_attachment_text_injected_but_stored_clean(self):
		file_doc = self._file()
		captured, chat = self._capture()
		with patch.object(Model, "chat", side_effect=chat):
			payload = start_run("summarize this", agent=self.agent.name, attachments=[file_doc.name])

		user_msg = [m for m in captured[0] if m["role"] == "user"][-1]
		self.assertIn("the secret code is 1234", user_msg["content"])
		self.assertIn("summarize this", user_msg["content"])

		session = frappe.get_doc("Flow Session", payload["session"])
		stored_user = [m for m in session.messages if m.role == "user"][-1]
		self.assertEqual(stored_user.content, "summarize this")

		self.assertEqual(len(session.attachments), 1)
		attachment = session.attachments[0]
		self.assertEqual(attachment.file, file_doc.name)
		self.assertEqual(attachment.run, payload["name"])
		self.assertEqual(attachment.extracted_text, "the secret code is 1234")

	def test_attachment_replayed_on_later_turn(self):
		file_doc = self._file()
		captured, chat = self._capture()
		with patch.object(Model, "chat", side_effect=chat):
			first = start_run("turn one", agent=self.agent.name, attachments=[file_doc.name])
			start_run("turn two", session=first["session"])

		# File stays in context for the whole conversation: turn one's file is re-sent on turn two.
		turn_two_users = [m for m in captured[1] if m["role"] == "user"]
		self.assertEqual(turn_two_users[-1]["content"], "turn two")
		self.assertIn("the secret code is 1234", turn_two_users[0]["content"])

	def test_attachment_visible_on_resume(self):
		file_doc = self._file()
		with patch.object(Model, "chat", return_value=_confirm_call()):
			paused = start_run("do it", agent=self.agent.name, attachments=[file_doc.name])
		self.assertEqual(paused["status"], "Paused")

		captured, chat = self._capture()
		with patch.object(Model, "chat", side_effect=chat):
			resume_run(paused["name"], {"c1": "use a different approach"})

		user_msgs = [m for m in captured[0] if m["role"] == "user"]
		self.assertIn("the secret code is 1234", user_msgs[0]["content"])

	def test_duplicate_attachment_is_recorded_once(self):
		file_doc = self._file()
		with patch.object(Model, "chat", return_value=_final()):
			payload = start_run("hi", agent=self.agent.name, attachments=[file_doc.name, file_doc.name])

		session = frappe.get_doc("Flow Session", payload["session"])
		self.assertEqual(len(session.attachments), 1)

	def test_attachments_accepts_json_string(self):
		file_doc = self._file()
		captured, chat = self._capture()
		with patch.object(Model, "chat", side_effect=chat):
			start_run("hi", agent=self.agent.name, attachments=json.dumps([file_doc.name]))

		user_msg = [m for m in captured[0] if m["role"] == "user"][-1]
		self.assertIn("the secret code is 1234", user_msg["content"])

	def test_invalid_attachments_payload_rejected(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Attachments"):
			start_run("hi", agent=self.agent.name, attachments="not json")

	def test_unreadable_attachment_aborts_turn(self):
		with self.assertRaises(frappe.DoesNotExistError):
			start_run("hi", agent=self.agent.name, attachments=["nonexistent-file-id"])


class TestAttachFile(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def _file(self, file_name: str = "report.txt", content: str = "report body"):
		return frappe.get_doc(
			{"doctype": "File", "file_name": file_name, "content": content, "is_private": 1}
		).insert()

	def test_attach_file_returns_chip_metadata_and_stages_text(self):
		from flow.flow.doctype.flow_session_attachment.flow_session_attachment import staged_attachment

		file_doc = self._file()
		chip = attach_file(file_doc.name)

		self.assertEqual(chip["file"], file_doc.name)
		self.assertEqual(chip["file_name"], "report.txt")
		self.assertNotIn("extracted_text", chip)
		self.assertEqual(staged_attachment(file_doc.name)["extracted_text"], "report body")

	def test_attach_file_strips_and_resolves_input(self):
		file_doc = self._file()
		chip = attach_file(f"  {file_doc.name}  ")
		self.assertEqual(chip["file"], file_doc.name)

	def test_attach_file_rejects_empty_input(self):
		with self.assertRaisesRegex(frappe.ValidationError, "File is required"):
			attach_file("")

	def test_attach_file_rejects_whitespace_input(self):
		with self.assertRaisesRegex(frappe.ValidationError, "File is required"):
			attach_file("   ")

	def test_attach_file_unsupported_type_surfaces_at_upload(self):
		file_doc = self._file(file_name="data.bin", content="x")
		with self.assertRaisesRegex(frappe.ValidationError, "Unsupported file type"):
			attach_file(file_doc.name)


def _ensure_user(email: str) -> str:
	if frappe.db.exists("User", email):
		return email
	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": email.split("@")[0],
			"send_welcome_email": 0,
			"enabled": 1,
		}
	)
	user.insert(ignore_permissions=True)
	return email


class TestParseAttachments(IntegrationTestCase):
	def test_empty_values_return_empty_list(self):
		for value in (None, "", [], "[]"):
			with self.subTest(value=value):
				self.assertEqual(_parse_attachments(value), [])

	def test_list_of_ids_passthrough(self):
		self.assertEqual(_parse_attachments(["a", "b"]), ["a", "b"])

	def test_json_string_array_parsed(self):
		self.assertEqual(_parse_attachments('["a", "b"]'), ["a", "b"])

	def test_whitespace_stripped(self):
		self.assertEqual(_parse_attachments(["  a  ", "b\n"]), ["a", "b"])

	def test_invalid_json_rejected(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Attachments"):
			_parse_attachments("not json")

	def test_non_list_json_rejected(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Attachments"):
			_parse_attachments('{"a": 1}')

	def test_non_string_item_rejected(self):
		with self.assertRaisesRegex(frappe.ValidationError, "file id"):
			_parse_attachments(["ok", 123])

	def test_blank_item_rejected(self):
		with self.assertRaisesRegex(frappe.ValidationError, "file id"):
			_parse_attachments(["ok", "   "])


class TestRecoverSession(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def _session(self) -> str:
		return frappe.get_doc({"doctype": "Flow Session"}).insert(ignore_permissions=True).name

	def _run(self, session: str, status: str, **fields) -> str:
		return (
			frappe.get_doc(
				{"doctype": "Flow Run", "session": session, "source": "Manual", "status": status, **fields}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def test_running_run_is_marked_failed(self):
		session = self._session()
		run = self._run(session, "Running")

		self.assertEqual(recover_session(session), {"recovered": 1})
		doc = frappe.get_doc("Flow Run", run)
		self.assertEqual(doc.status, "Failed")
		self.assertIn("abandoned", doc.error)

	def test_completed_and_paused_runs_untouched(self):
		session = self._session()
		completed = self._run(session, "Completed")
		paused = self._run(session, "Paused", questions=json.dumps([{"key": "c1"}]))

		self.assertEqual(recover_session(session), {"recovered": 0})
		self.assertEqual(frappe.db.get_value("Flow Run", completed, "status"), "Completed")
		self.assertEqual(frappe.db.get_value("Flow Run", paused, "status"), "Paused")

	def test_no_runs_is_noop(self):
		self.assertEqual(recover_session(self._session()), {"recovered": 0})

	def test_other_users_session_is_rejected(self):
		session = self._session()
		self._run(session, "Running")

		frappe.set_user(_ensure_user("recover-other-user@example.com"))
		with self.assertRaises(frappe.PermissionError):
			recover_session(session)

	def test_blank_session_raises(self):
		with self.assertRaisesRegex(frappe.ValidationError, "required"):
			recover_session("  ")


class TestSubmitFeedback(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sync_builtin_tools()

	def setUp(self):
		self.model = frappe.get_doc(_model_doc(title="Feedback Test Model")).insert()
		self.agent = frappe.get_doc(
			_agent_doc(self.model.name, title="Feedback Test Agent", tools=[{"tool": "update_memory"}])
		).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		memory_store.drop_table()

	def _run(self, status: str = "Completed", agent: str | None = None, **fields) -> str:
		session = frappe.get_doc({"doctype": "Flow Session", "agent": agent or self.agent.name}).insert(
			ignore_permissions=True
		)
		return (
			frappe.get_doc(
				{
					"doctype": "Flow Run",
					"session": session.name,
					"source": "Manual",
					"status": status,
					**fields,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def test_up_rating_persists(self):
		run = self._run()
		self.assertEqual(submit_feedback(run, "Up"), {"rating": "Up"})
		self.assertEqual(frappe.db.get_value("Flow Run", run, "feedback_rating"), "Up")

	def test_down_with_comment_persists(self):
		run = self._run()
		submit_feedback(run, "Down", comment="Wrong item code.")
		doc = frappe.get_doc("Flow Run", run)
		self.assertEqual(doc.feedback_rating, "Down")
		self.assertEqual(doc.feedback_comment, "Wrong item code.")

	def test_rejects_invalid_rating(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Rating"):
			submit_feedback(self._run(), "Sideways")

	def test_rejects_unfinished_run(self):
		with self.assertRaisesRegex(frappe.ValidationError, "finished"):
			submit_feedback(self._run(status="Running"), "Up")

	def test_rejects_overlong_comment(self):
		with self.assertRaisesRegex(frappe.ValidationError, "characters"):
			submit_feedback(self._run(), "Down", comment="x" * 501)

	def test_rejects_other_users_run(self):
		run = self._run()
		frappe.set_user(_ensure_user("feedback-other-user@example.com"))
		with self.assertRaises(frappe.PermissionError):
			submit_feedback(run, "Up")

	def test_down_comment_saved_as_memory(self):
		run = self._run()
		result = submit_feedback(run, "Down", comment="Widget A maps to WGT-001.")
		memory = frappe.get_doc("Flow Agent Memory", result["memory"])
		self.assertEqual(memory.agent, self.agent.name)
		self.assertEqual(memory.scope, "Agent")
		self.assertEqual(memory.source, "Feedback")
		self.assertEqual(memory.source_run, run)
		self.assertEqual(memory.content, "Widget A maps to WGT-001.")

	def test_down_comment_without_memory_tool_records_but_skips_memory(self):
		other = frappe.get_doc(_agent_doc(self.model.name, title="Feedback No Memory Agent")).insert()
		run = self._run(agent=other.name)
		result = submit_feedback(run, "Down", comment="Fix it.")
		self.assertNotIn("memory", result)
		self.assertEqual(frappe.db.get_value("Flow Run", run, "feedback_rating"), "Down")
		self.assertFalse(frappe.db.exists("Flow Agent Memory", {"agent": other.name}))

	def test_up_never_saves_memory(self):
		result = submit_feedback(self._run(), "Up", comment="Nice.")
		self.assertNotIn("memory", result)
		self.assertFalse(frappe.db.exists("Flow Agent Memory", {"agent": self.agent.name}))

	def test_down_without_comment_saves_no_memory(self):
		result = submit_feedback(self._run(), "Down")
		self.assertNotIn("memory", result)
		self.assertFalse(frappe.db.exists("Flow Agent Memory", {"agent": self.agent.name}))

	def test_none_clears_rating(self):
		run = self._run()
		submit_feedback(run, "Down", comment="Not quite.")
		self.assertEqual(submit_feedback(run, "None"), {"rating": None})
		doc = frappe.get_doc("Flow Run", run)
		self.assertFalse(doc.feedback_rating)
		self.assertIsNone(doc.feedback_comment)

	def test_none_keeps_saved_memory(self):
		run = self._run()
		result = submit_feedback(run, "Down", comment="Widget A maps to WGT-001.")
		submit_feedback(run, "None")
		self.assertTrue(frappe.db.exists("Flow Agent Memory", result["memory"]))


class TestMemoryRunProvenance(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sync_builtin_tools()

	def setUp(self):
		self.model = frappe.get_doc(_model_doc(title="Provenance Model")).insert()
		self.agent = frappe.get_doc(
			_agent_doc(self.model.name, title="Provenance Agent", tools=[{"tool": "update_memory"}])
		).insert()

	def tearDown(self):
		frappe.flags.flow_run = None
		frappe.db.rollback()
		memory_store.drop_table()

	def test_agent_memory_stamped_with_run_then_flag_cleared(self):
		with patch.object(Model, "chat", side_effect=[_memory_call(), _final("done")]):
			payload = start_run("remember the mapping", agent=self.agent.name)

		self.assertEqual(payload["status"], "Completed")
		memory = frappe.get_doc("Flow Agent Memory", {"agent": self.agent.name})
		self.assertEqual(memory.source, "Agent")
		self.assertEqual(memory.source_run, payload["name"])
		# The flag must not linger past the run that set it.
		self.assertIsNone(frappe.flags.get("flow_run"))

	def test_flag_cleared_when_run_fails(self):
		def boom(self, messages, tools=None, *, stream=False):
			raise RuntimeError("kaboom")

		with patch.object(Model, "chat", new=boom):
			with self.assertRaises(RuntimeError):
				start_run("go", agent=self.agent.name)
		self.assertIsNone(frappe.flags.get("flow_run"))
