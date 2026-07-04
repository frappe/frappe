# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from flow.flow.doctype.flow_session.flow_session import (
	CHARS_PER_TOKEN,
	DEFAULT_CONTEXT_WINDOW,
	RESERVED_OUTPUT_TOKENS,
	RETRIEVAL_FRACTION,
	FlowSession,
	_clamp,
	_embeddings_configured,
	_inject_inline_files,
	_inject_retrieved_chunks,
	_note_retrieval_files,
	_route_attachment,
	derive_title,
)


class TestFlowSession(IntegrationTestCase):
	def setUp(self):
		self.model = frappe.get_doc(
			{
				"doctype": "Flow Model",
				"title": "Session Test Model",
				"model_id": "openai/gpt-4o-mini",
				"enabled": 1,
			}
		).insert()
		self.agent = frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Session Test Agent",
				"model": self.model.name,
				"instructions": "x",
				"enabled": 1,
			}
		).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_session_can_be_created_without_agent(self):
		# Code-defined agents drive sessions without a doctype agent link.
		doc = frappe.get_doc({"doctype": "Flow Session", "title": "chat 1"}).insert(ignore_permissions=True)

		self.assertIsNone(doc.agent)

	def test_session_can_be_created_without_title(self):
		doc = frappe.get_doc({"doctype": "Flow Session", "agent": self.agent.name}).insert(
			ignore_permissions=True
		)

		self.assertIsNone(doc.title)

	def test_session_agent_is_locked_after_creation(self):
		other_agent = frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Other Session Agent",
				"model": self.model.name,
				"instructions": "x",
				"enabled": 1,
			}
		).insert()
		doc = frappe.get_doc({"doctype": "Flow Session", "agent": self.agent.name}).insert(
			ignore_permissions=True
		)

		doc.agent = other_agent.name
		with self.assertRaisesRegex(frappe.ValidationError, "Cannot change the agent"):
			doc.save(ignore_permissions=True)


class TestClearOldLogs(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def _session_with_run(self, *, age_days: int) -> tuple[str, str, str]:
		f = frappe.get_doc({"doctype": "File", "file_name": "f.txt", "content": "x", "is_private": 1}).insert(
			ignore_permissions=True
		)
		session = frappe.get_doc({"doctype": "Flow Session", "title": "chat"})
		session.append("messages", {"role": "user", "content": "hi"})
		session.append("attachments", {"file": f.name, "file_name": "f.txt", "file_size": 1})
		session.insert(ignore_permissions=True)
		run = frappe.get_doc(
			{"doctype": "Flow Run", "session": session.name, "source": "Manual", "status": "Completed"}
		).insert(ignore_permissions=True)
		old = frappe.utils.add_days(frappe.utils.now(), -age_days)
		frappe.db.set_value("Flow Session", session.name, "modified", old, update_modified=False)
		return session.name, run.name, f.name

	def test_old_session_and_linked_run_and_messages_are_purged(self):
		old_session, old_run, old_file = self._session_with_run(age_days=100)

		FlowSession.clear_old_logs(days=30)

		self.assertFalse(frappe.db.exists("Flow Session", old_session))
		self.assertFalse(frappe.db.exists("Flow Run", old_run))
		self.assertEqual(frappe.db.count("Flow Session Message", {"parent": old_session}), 0)
		self.assertEqual(frappe.db.count("Flow Session Attachment", {"parent": old_session}), 0)
		self.assertFalse(frappe.db.exists("File", old_file))

	def test_recent_session_is_kept(self):
		recent_session, recent_run, recent_file = self._session_with_run(age_days=1)

		FlowSession.clear_old_logs(days=30)

		self.assertTrue(frappe.db.exists("Flow Session", recent_session))
		self.assertTrue(frappe.db.exists("Flow Run", recent_run))
		self.assertTrue(frappe.db.exists("File", recent_file))


class TestDeriveTitle(IntegrationTestCase):
	def test_short_text_returned_as_is(self):
		self.assertEqual(derive_title("hello world"), "hello world")

	def test_long_text_truncated_with_ellipsis(self):
		long_input = "a" * 200
		result = derive_title(long_input)

		self.assertEqual(len(result), 80)
		self.assertTrue(result.endswith("…"))

	def test_whitespace_collapsed(self):
		self.assertEqual(derive_title("hello   \n  world"), "hello world")

	def test_empty_input_returns_empty_string(self):
		self.assertEqual(derive_title(""), "")
		self.assertEqual(derive_title(None), "")


def _att(file_name="f.txt", extracted_text="", mode="Inline", run=None):
	return SimpleNamespace(file_name=file_name, extracted_text=extracted_text, mode=mode, run=run)


class TestAttachmentRouting(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_small_file_is_inline(self):
		self.assertEqual(_route_attachment("x" * 100, threshold=1000, embeddings_on=True), "Inline")

	def test_at_threshold_is_inline(self):
		self.assertEqual(_route_attachment("x" * 1000, threshold=1000, embeddings_on=True), "Inline")

	def test_oversized_with_embeddings_is_retrieval(self):
		self.assertEqual(_route_attachment("x" * 2000, threshold=1000, embeddings_on=True), "Retrieval")

	def test_oversized_without_embeddings_stays_inline(self):
		self.assertEqual(_route_attachment("x" * 2000, threshold=1000, embeddings_on=False), "Inline")

	def test_none_text_is_inline(self):
		self.assertEqual(_route_attachment(None, threshold=1000, embeddings_on=True), "Inline")

	def test_embeddings_configured_reflects_settings(self):
		frappe.db.set_single_value("Flow Knowledge Settings", "embedding_model", "")
		frappe.clear_document_cache("Flow Knowledge Settings", "Flow Knowledge Settings")
		self.assertFalse(_embeddings_configured())


class TestAttachmentInjection(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_inline_injects_full_text_and_decrements_budget(self):
		content, budget = _inject_inline_files("hi", [_att(extracted_text="FULLBODY")], 1000)
		self.assertIn("FULLBODY", content)
		self.assertIn("f.txt", content)
		self.assertEqual(budget, 1000 - len("FULLBODY"))

	def test_inline_truncates_over_budget_with_marker(self):
		content, budget = _inject_inline_files("", [_att(extracted_text="X" * 100)], 10)
		self.assertIn("truncated", content.lower())
		self.assertEqual(budget, 0)

	def test_note_names_files(self):
		note = _note_retrieval_files("q", [_att(file_name="report.pdf")])
		self.assertIn("report.pdf", note)

	def test_chunks_injected_within_budget(self):
		content, _ = _inject_retrieved_chunks("q", [{"content": "ALPHA"}, {"content": "BETA"}], 1000)
		self.assertIn("ALPHA", content)
		self.assertIn("BETA", content)

	def test_chunks_stop_at_budget(self):
		content, budget = _inject_retrieved_chunks("q", [{"content": "X" * 100}], 5)
		self.assertEqual(budget, 0)
		self.assertIn("Relevant", content)

	def test_no_chunks_leaves_content_unchanged(self):
		content, budget = _inject_retrieved_chunks("q", [], 1000)
		self.assertEqual(content, "q")
		self.assertEqual(budget, 1000)

	def test_clamp_within_over_and_zero(self):
		self.assertEqual(_clamp("hello", 10), ("hello", False))
		self.assertEqual(_clamp("hello", 3), ("hel", True))
		self.assertEqual(_clamp("hello", 0), ("", True))


class TestAttachmentBudget(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def _session(self, snapshot=None):
		s = frappe.get_doc({"doctype": "Flow Session"}).insert(ignore_permissions=True)
		s._snapshot = snapshot if snapshot is not None else {"model": None}
		return s

	def test_context_window_defaults_when_model_unknown(self):
		self.assertEqual(self._session()._context_window(), DEFAULT_CONTEXT_WINDOW)

	def test_context_window_reads_model_field(self):
		model = frappe.get_doc(
			{
				"doctype": "Flow Model",
				"title": "CW Model",
				"model_id": "openai/gpt-4o-mini",
			}
		).insert()
		frappe.db.set_value("Flow Model", model.name, "context_window", 9000)
		self.assertEqual(self._session({"model": model.name})._context_window(), 9000)

	def test_inline_threshold_is_fraction_of_window(self):
		expected = int(DEFAULT_CONTEXT_WINDOW * CHARS_PER_TOKEN * RETRIEVAL_FRACTION)
		self.assertEqual(self._session()._attachment_inline_threshold(), expected)

	def test_budget_shrinks_with_dialogue(self):
		s = self._session()
		base = DEFAULT_CONTEXT_WINDOW * CHARS_PER_TOKEN - RESERVED_OUTPUT_TOKENS * CHARS_PER_TOKEN
		self.assertEqual(s._file_injection_budget(), base)  # no messages yet
		s.append("messages", {"role": "user", "content": "x" * 500, "run": None})
		s.save(ignore_permissions=True)
		s._snapshot = {"model": None}
		self.assertEqual(s._file_injection_budget(), base - 500)

	def test_budget_floors_at_zero(self):
		model = frappe.get_doc(
			{"doctype": "Flow Model", "title": "Tiny", "model_id": "openai/gpt-4o-mini"}
		).insert()
		frappe.db.set_value("Flow Model", model.name, "context_window", 1)
		s = self._session({"model": model.name})
		s.append("messages", {"role": "user", "content": "x" * 10000, "run": None})
		s.save(ignore_permissions=True)
		s._snapshot = {"model": model.name}
		self.assertEqual(s._file_injection_budget(), 0)


class TestBuildPromptMessages(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def _file(self):
		return frappe.get_doc(
			{"doctype": "File", "file_name": "f.txt", "content": "x", "is_private": 1}
		).insert(ignore_permissions=True)

	def test_inline_full_text_injected_on_its_turn(self):
		s = frappe.get_doc({"doctype": "Flow Session"}).insert(ignore_permissions=True)
		s._snapshot = {"model": None}
		f = self._file()
		s.append("messages", {"role": "user", "content": "summarize", "run": None})
		s.append(
			"attachments",
			{
				"file": f.name,
				"file_name": "f.txt",
				"file_size": 3,
				"extracted_text": "INLINEBODY",
				"mode": "Inline",
			},
		)
		s.save(ignore_permissions=True)
		content = next(m for m in s._build_prompt_messages() if m["role"] == "user")["content"]
		self.assertIn("INLINEBODY", content)

	def test_retrieval_injects_chunks_not_full_text(self):
		s = frappe.get_doc({"doctype": "Flow Session"}).insert(ignore_permissions=True)
		s._snapshot = {"model": None}
		f = self._file()
		big = "SECRETFULLTEXT " * 50
		s.append("messages", {"role": "user", "content": "what does it say", "run": None})
		s.append(
			"attachments",
			{
				"file": f.name,
				"file_name": "big.txt",
				"file_size": len(big),
				"extracted_text": big,
				"mode": "Retrieval",
			},
		)
		s.save(ignore_permissions=True)
		with patch(
			"flow.knowledge.retriever.retrieve_attachments", return_value=[{"content": "CHUNKED_EXCERPT"}]
		):
			content = next(m for m in s._build_prompt_messages() if m["role"] == "user")["content"]
		self.assertIn("big.txt", content)  # note marks the attachment
		self.assertIn("CHUNKED_EXCERPT", content)  # excerpt injected
		self.assertNotIn("SECRETFULLTEXT", content)  # full text NOT injected

	def test_no_attachments_leaves_message_clean(self):
		s = frappe.get_doc({"doctype": "Flow Session"}).insert(ignore_permissions=True)
		s._snapshot = {"model": None}
		s.append("messages", {"role": "user", "content": "hello", "run": None})
		s.save(ignore_permissions=True)
		content = next(m for m in s._build_prompt_messages() if m["role"] == "user")["content"]
		self.assertEqual(content, "hello")


class TestIndexRetrievalAttachments(IntegrationTestCase):
	def setUp(self):
		frappe.db.set_single_value("Flow Knowledge Settings", "chunk_size", 200)
		frappe.db.set_single_value("Flow Knowledge Settings", "chunk_overlap", 20)
		frappe.db.set_single_value("Flow Knowledge Settings", "embedding_dimension", 4)
		frappe.clear_document_cache("Flow Knowledge Settings", "Flow Knowledge Settings")

	def tearDown(self):
		frappe.db.rollback()

	def _session_with_retrieval(self, text):
		f = frappe.get_doc({"doctype": "File", "file_name": "f.txt", "content": "x", "is_private": 1}).insert(
			ignore_permissions=True
		)
		s = frappe.get_doc({"doctype": "Flow Session"}).insert(ignore_permissions=True)
		s.append(
			"attachments",
			{
				"file": f.name,
				"file_name": "f.txt",
				"file_size": len(text),
				"extracted_text": text,
				"mode": "Retrieval",
				"run": None,
			},
		)
		s.save(ignore_permissions=True)
		return s

	def test_indexes_chunks_and_keeps_retrieval_mode(self):
		s = self._session_with_retrieval("Revenue grew twelve percent this quarter. " * 20)
		with (
			patch(
				"flow.knowledge.embedder.embed_texts",
				side_effect=lambda chunks: [[1.0, 0.0, 0.0, 0.0]] * len(chunks),
			),
			patch("flow.knowledge.attachment_store.ensure_table"),
			patch("flow.knowledge.attachment_store.add") as add,
		):
			s._index_retrieval_attachments(None)
		add.assert_called_once()
		s.reload()
		self.assertEqual(s.attachments[0].mode, "Retrieval")

	def test_empty_text_demotes_to_inline(self):
		s = self._session_with_retrieval("   ")
		with patch("flow.knowledge.embedder.embed_texts") as embed:
			s._index_retrieval_attachments(None)
		embed.assert_not_called()  # nothing to chunk -> no embedding
		s.reload()
		self.assertEqual(s.attachments[0].mode, "Inline")

	def test_embedding_failure_demotes_to_inline(self):
		s = self._session_with_retrieval("Some content worth chunking. " * 20)
		with patch("flow.knowledge.embedder.embed_texts", side_effect=RuntimeError("provider down")):
			s._index_retrieval_attachments(None)
		s.reload()
		self.assertEqual(s.attachments[0].mode, "Inline")


class TestAttachmentCleanup(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_on_trash_purges_session_chunks(self):
		s = frappe.get_doc({"doctype": "Flow Session"}).insert(ignore_permissions=True)
		with patch("flow.knowledge.attachment_store.delete") as delete:
			frappe.delete_doc("Flow Session", s.name, ignore_permissions=True)
		delete.assert_called_once_with(session=s.name)

	def test_cleanup_failure_does_not_block_delete(self):
		s = frappe.get_doc({"doctype": "Flow Session"}).insert(ignore_permissions=True)
		with patch("flow.knowledge.attachment_store.delete", side_effect=RuntimeError("store down")):
			frappe.delete_doc("Flow Session", s.name, ignore_permissions=True)
		self.assertFalse(frappe.db.exists("Flow Session", s.name))

	def test_on_trash_deletes_linked_runs(self):
		s = frappe.get_doc({"doctype": "Flow Session"}).insert(ignore_permissions=True)
		run = frappe.get_doc(
			{"doctype": "Flow Run", "session": s.name, "source": "Manual", "status": "Completed"}
		).insert(ignore_permissions=True)
		with patch("flow.knowledge.attachment_store.delete"):
			frappe.delete_doc("Flow Session", s.name, ignore_permissions=True)
		self.assertFalse(frappe.db.exists("Flow Run", run.name))

	def test_clear_old_logs_purges_chunks_for_batch(self):
		s = frappe.get_doc({"doctype": "Flow Session", "title": "old"}).insert(ignore_permissions=True)
		old = frappe.utils.add_days(frappe.utils.now(), -100)
		frappe.db.set_value("Flow Session", s.name, "modified", old, update_modified=False)
		with patch("flow.knowledge.attachment_store.delete") as delete:
			FlowSession.clear_old_logs(days=30)
		batch = delete.call_args.kwargs["session"]
		self.assertIn(s.name, batch)
