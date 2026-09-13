# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import io
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from PIL import Image

from flow.flow.doctype.flow_session_attachment.flow_session_attachment import (
	MAX_ATTACHMENTS,
	TRUNCATED,
	build_turn,
	load_attachment,
	stage_attachment,
	staged_attachment,
)

MODULE = "flow.flow.doctype.flow_session_attachment.flow_session_attachment"
VISION = "flow_harness.model.catalog.model_supports_images"
LARGE_NOTE = "[Attached file: {0} (large; relevant excerpts follow)]"


def _file(file_name="note.txt", content="attachment body", **kwargs):
	return frappe.get_doc(
		{"doctype": "File", "file_name": file_name, "content": content, "is_private": 1, **kwargs}
	).insert(ignore_permissions=True)


def png_bytes(text: str | None = None) -> bytes:
	"""A small PNG; with `text`, one that OCR can read."""
	from PIL import ImageDraw

	image = Image.new("RGB", (400, 80), "white")
	if text:
		ImageDraw.Draw(image).text((10, 20), text, fill="black")
	buffer = io.BytesIO()
	image.save(buffer, format="PNG")
	return buffer.getvalue()


def _ensure_user(email):
	if frappe.db.exists("User", email):
		return email
	frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": email.split("@")[0],
			"send_welcome_email": 0,
			"enabled": 1,
		}
	).insert(ignore_permissions=True)
	return email


class TestLoadAttachment(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_extracts_text_and_metadata(self):
		file_doc = _file(content="attachment body")
		data, _file_doc = load_attachment(file_doc.name)
		self.assertEqual(data["file"], file_doc.name)
		self.assertEqual(data["file_name"], "note.txt")
		self.assertEqual(data["file_size"], file_doc.file_size)
		self.assertEqual(data["extracted_text"], "attachment body")

	def test_images_are_not_read_at_upload(self):
		file_doc = _file(file_name="pic.png", content=png_bytes())
		with patch(f"{MODULE}.extract_file") as extract:
			data, _file_doc = load_attachment(file_doc.name)
		extract.assert_not_called()
		self.assertIsNone(data["extracted_text"])

	def test_rejects_unsupported_extension(self):
		file_doc = _file(file_name="data.bin", content="x")
		with self.assertRaisesRegex(frappe.ValidationError, "Unsupported file type"):
			load_attachment(file_doc.name)

	def test_rejects_empty_text(self):
		file_doc = _file(file_name="blank.txt", content="   ")
		with self.assertRaisesRegex(frappe.ValidationError, "No readable text"):
			load_attachment(file_doc.name)

	def test_rejects_file_not_readable_by_user(self):
		# Owned by Administrator and private: a regular user must not be able to attach it.
		file_doc = _file(content="secret body")
		frappe.set_user(_ensure_user("attach-other@example.com"))
		with self.assertRaises(frappe.PermissionError):
			load_attachment(file_doc.name)

	def test_owner_can_attach_own_file(self):
		frappe.set_user(_ensure_user("attach-owner@example.com"))
		file_doc = _file(file_name="mine.txt", content="my own notes")
		data, _file_doc = load_attachment(file_doc.name)
		self.assertEqual(data["extracted_text"], "my own notes")


class TestStageAttachment(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_stage_caches_extraction_and_returns_chip_metadata(self):
		file_doc = _file(content="staged body")
		chip = stage_attachment(file_doc.name)
		self.assertEqual(set(chip), {"file", "file_name", "file_size"})
		self.assertEqual(chip["file"], file_doc.name)
		self.assertEqual(staged_attachment(file_doc.name)["extracted_text"], "staged body")

	def test_staged_attachment_is_user_scoped(self):
		file_doc = _file(content="staged body")
		stage_attachment(file_doc.name)  # cached under Administrator
		frappe.set_user(_ensure_user("attach-scope@example.com"))
		self.assertIsNone(staged_attachment(file_doc.name))

	def test_staged_attachment_missing_returns_none(self):
		self.assertIsNone(staged_attachment("no-such-file"))


class TestBuildTurn(IntegrationTestCase):
	"""How files fold into one turn's message, uploads and attachment rows."""

	def setUp(self):
		self.model = frappe.get_doc(
			{"doctype": "Flow Model", "title": "Turn Model", "model_id": "openai/gpt-4o-mini", "enabled": 1}
		).insert()
		agent = frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Turn Agent",
				"model": self.model.name,
				"instructions": "x",
				"enabled": 1,
			}
		).insert()
		self.session = frappe.get_doc({"doctype": "Flow Session", "agent": agent.name}).insert(
			ignore_permissions=True
		)
		for field, value in (("chunk_size", 200), ("chunk_overlap", 20), ("embedding_dimension", 4)):
			frappe.db.set_single_value("Flow Knowledge Settings", field, value)
		frappe.clear_document_cache("Flow Knowledge Settings", "Flow Knowledge Settings")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def shrink_window(self, tokens: int) -> None:
		frappe.db.set_value("Flow Model", self.model.name, "context_window", tokens)

	def enable_embeddings(self):
		frappe.db.set_single_value("Flow Knowledge Settings", "embedding_model", self.model.name)
		frappe.clear_document_cache("Flow Knowledge Settings", "Flow Knowledge Settings")
		self.enterContext(
			patch("flow.knowledge.embedder.embed_texts", side_effect=lambda t: [[1.0, 0, 0, 0]] * len(t))
		)
		self.enterContext(patch("flow.knowledge.attachment_store.ensure_table"))
		self.index_delete = self.enterContext(patch("flow.knowledge.attachment_store.delete"))
		self.enterContext(
			patch("flow.knowledge.retriever.retrieve_attachments", return_value=[{"content": "EXCERPT"}])
		)
		return self.enterContext(patch("flow.knowledge.attachment_store.add"))

	def test_text_is_inlined_with_the_servers_file_marker(self):
		file_doc = _file(file_name="q&a.txt", content="the body")
		turn = build_turn(self.session, "summarize", [file_doc.name])
		self.assertEqual(turn.message, 'summarize\n<file name="q&amp;a.txt">\nthe body\n</file>')
		self.assertEqual(turn.images, [])
		self.assertEqual(
			turn.attachment_rows,
			[
				{
					"file": file_doc.name,
					"file_name": "q&a.txt",
					"file_size": file_doc.file_size,
					"mode": "Inline",
					"extracted_text": "the body",
				}
			],
		)

	def test_a_file_named_twice_is_sent_once(self):
		file_doc = _file()
		turn = build_turn(self.session, "hi", [file_doc.name, file_doc.name])
		self.assertEqual(len(turn.attachment_rows), 1)
		self.assertEqual(turn.message.count("<file "), 1)

	def test_too_many_files_are_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "at most"):
			build_turn(self.session, "hi", [f"f{i}" for i in range(MAX_ATTACHMENTS + 1)])

	def test_no_files_leaves_the_message_alone(self):
		turn = build_turn(self.session, "hello", [])
		self.assertEqual((turn.message, turn.images, turn.attachment_rows), ("hello", [], []))

	def test_oversized_text_without_embeddings_is_truncated_inline(self):
		self.shrink_window(10)  # 20 characters of file text
		file_doc = _file(file_name="big.txt", content="A" * 30)
		turn = build_turn(self.session, "hi", [file_doc.name])
		self.assertEqual(turn.message, f'hi\n<file name="big.txt">\n{"A" * 20}\n{TRUNCATED}\n</file>')
		self.assertEqual(
			(turn.attachment_rows[0]["mode"], turn.attachment_rows[0]["extracted_text"]), ("Inline", "A" * 30)
		)

	def test_the_fixed_budget_is_shared_across_inline_files(self):
		self.shrink_window(10)  # 20 characters for exact attachment text this turn
		first = _file(file_name="first.txt", content="A" * 15)
		second = _file(file_name="second.txt", content="B" * 15)
		turn = build_turn(self.session, "hi", [first.name, second.name])
		self.assertIn(f'<file name="first.txt">\n{"A" * 15}\n</file>', turn.message)
		self.assertIn(f'<file name="second.txt">\n{"B" * 5}\n{TRUNCATED}\n</file>', turn.message)
		self.assertEqual([row["extracted_text"] for row in turn.attachment_rows], ["A" * 15, "B" * 15])

	def test_only_the_largest_files_move_to_retrieval_when_the_set_exceeds_the_budget(self):
		self.shrink_window(10)
		add = self.enable_embeddings()
		large = _file(file_name="large.txt", content="A" * 16)
		small = _file(file_name="small.txt", content="B" * 8)
		turn = build_turn(self.session, "hi", [large.name, small.name])
		self.assertEqual([row["mode"] for row in turn.attachment_rows], ["Retrieval", "Inline"])
		self.assertIn(LARGE_NOTE.format("large.txt"), turn.message)
		self.assertIn(f'<file name="small.txt">\n{"B" * 8}\n</file>', turn.message)
		self.assertEqual(add.call_args.args[1], large.name)

	def test_oversized_text_with_embeddings_is_indexed_and_excerpted(self):
		self.shrink_window(10)
		add = self.enable_embeddings()
		file_doc = _file(file_name="big.txt", content="word " * 100)
		turn = build_turn(self.session, "what does it say", [file_doc.name])
		self.assertEqual(
			turn.message,
			f"what does it say\n{LARGE_NOTE.format('big.txt')}\n"
			"Relevant excerpts from the attached files:\n<excerpts>\nEXCERPT\n</excerpts>",
		)
		self.assertEqual(
			(turn.attachment_rows[0]["mode"], turn.attachment_rows[0]["extracted_text"]),
			("Retrieval", ("word " * 100).strip()),
		)
		session, key, chunks, vectors = add.call_args.args
		self.assertEqual((session, key, len(chunks), len(vectors)), (self.session.name, file_doc.name, 3, 3))
		self.index_delete.assert_called_once_with(session=self.session.name, attachment=file_doc.name)

	def test_an_indexing_failure_is_surfaced(self):
		self.shrink_window(10)
		self.enable_embeddings()
		with (
			patch("flow.knowledge.embedder.embed_texts", side_effect=RuntimeError("provider down")),
			self.assertRaisesRegex(frappe.ValidationError, "Could not index"),
		):
			build_turn(self.session, "hi", [_file(file_name="big.txt", content="A" * 30).name])

	def test_reattaching_an_indexed_file_does_not_duplicate_its_chunks(self):
		self.shrink_window(10)
		add = self.enable_embeddings()
		file_doc = _file(file_name="big.txt", content="A" * 30)
		self.session.append(
			"attachments",
			{
				"file": file_doc.name,
				"file_name": file_doc.file_name,
				"file_size": file_doc.file_size,
				"mode": "Retrieval",
				"extracted_text": "A" * 30,
			},
		)
		build_turn(self.session, "again", [file_doc.name])
		add.assert_not_called()
		self.index_delete.assert_not_called()

	def test_later_turns_leave_the_message_alone(self):
		self.enable_embeddings()
		self.session.append(
			"attachments", {"file": _file().name, "file_name": "old.txt", "file_size": 1, "mode": "Retrieval"}
		)
		self.session.save(ignore_permissions=True)
		with patch("flow.knowledge.retriever.retrieve_attachments") as retrieve:
			turn = build_turn(self.session, "and now?", [])
		retrieve.assert_not_called()
		self.assertEqual((turn.message, turn.attachment_rows), ("and now?", []))

	def test_a_search_failure_is_surfaced(self):
		self.shrink_window(10)
		self.enable_embeddings()
		with (
			patch("flow.knowledge.retriever.retrieve_attachments", side_effect=RuntimeError("down")),
			self.assertRaisesRegex(frappe.ValidationError, "Could not search"),
		):
			build_turn(self.session, "hi", [_file(file_name="big.txt", content="A" * 30).name])

	def test_images_go_to_the_server_for_a_vision_model(self):
		data = png_bytes()
		file_doc = _file(file_name="pic.png", content=data)
		with patch(VISION, return_value=True) as sees:
			turn = build_turn(self.session, "what is this", [file_doc.name])
		sees.assert_called_once_with("openai/gpt-4o-mini")
		self.assertEqual(turn.message, "what is this")
		self.assertEqual(turn.images, [("pic.png", data, "image/png")])
		self.assertEqual(turn.attachment_rows[0]["mode"], "Image")
		self.assertNotIn("extracted_text", turn.attachment_rows[0])

	def test_an_unknown_models_images_are_sent_like_the_server_does(self):
		file_doc = _file(file_name="pic.png", content=png_bytes())
		with patch(VISION, return_value=None):
			turn = build_turn(self.session, "look", [file_doc.name])
		self.assertEqual(len(turn.images), 1)

	def test_images_are_read_by_ocr_for_a_text_only_model(self):
		file_doc = _file(file_name="pic.png", content=png_bytes())
		with patch(VISION, return_value=False), patch(f"{MODULE}.extract_file", return_value="OCR TEXT"):
			turn = build_turn(self.session, "read it", [file_doc.name])
		self.assertEqual(turn.message, 'read it\n<file name="pic.png">\nOCR TEXT\n</file>')
		self.assertEqual(turn.images, [])
		self.assertEqual(
			(turn.attachment_rows[0]["mode"], turn.attachment_rows[0]["extracted_text"]),
			("Inline", "OCR TEXT"),
		)

	def test_prepared_image_reuses_ocr_and_can_still_be_sent_to_a_vision_model(self):
		file_doc = _file(file_name="pic.png", content=png_bytes())
		with patch(f"{MODULE}.extract_file", return_value="OCR TEXT") as extract:
			stage_attachment(file_doc.name)
			extract.assert_called_once()
		with patch(f"{MODULE}.extract_file", side_effect=AssertionError("OCR repeated")):
			with patch(VISION, return_value=False):
				text_turn = build_turn(self.session, "read it", [file_doc.name])
			with patch(VISION, return_value=True):
				image_turn = build_turn(self.session, "look", [file_doc.name])
		self.assertIn("OCR TEXT", text_turn.message)
		self.assertEqual(len(image_turn.images), 1)
		self.assertEqual(image_turn.message, "look")

	def test_an_image_without_text_is_refused_for_a_text_only_model(self):
		file_doc = _file(file_name="pic.png", content=png_bytes())
		with (
			patch(VISION, return_value=False),
			patch(f"{MODULE}.extract_file", return_value=""),
			self.assertRaisesRegex(frappe.ValidationError, "No readable text found in pic.png"),
		):
			build_turn(self.session, "read it", [file_doc.name])

	def test_a_staged_file_is_rechecked_on_send(self):
		file_doc = _file(content="staged secret")
		stage_attachment(file_doc.name)
		with (
			patch(f"{MODULE}.frappe.has_permission", return_value=False),
			self.assertRaises(frappe.PermissionError),
		):
			build_turn(self.session, "hi", [file_doc.name])

	def test_a_file_the_user_cannot_read_is_refused(self):
		file_doc = _file(content="secret body")  # Administrator's private file
		frappe.set_user(_ensure_user("turn-other@example.com"))
		with self.assertRaises(frappe.PermissionError):
			build_turn(self.session, "hi", [file_doc.name])
