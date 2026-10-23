# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import io
from unittest.mock import patch

from PIL import Image

import frappe
from frappe.flow.doctype.flow_session_attachment.flow_session_attachment import (
	MAX_ATTACHMENTS,
	TRUNCATED,
	build_turn,
	load_attachment,
	stage_attachment,
	staged_attachment,
)
from frappe.tests import IntegrationTestCase

MODULE = "frappe.flow.doctype.flow_session_attachment.flow_session_attachment"
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

	def test_text_is_extracted_and_images_are_left_for_send(self):
		file_doc = _file(content="attachment body")
		data, _file_doc = load_attachment(file_doc.name)
		self.assertEqual(data["file"], file_doc.name)
		self.assertEqual(data["file_name"], "note.txt")
		self.assertEqual(data["file_size"], file_doc.file_size)
		self.assertEqual(data["extracted_text"], "attachment body")

		image = _file(file_name="pic.png", content=png_bytes())
		with patch(f"{MODULE}.extract_file") as extract:
			data, _file_doc = load_attachment(image.name)
		extract.assert_not_called()
		self.assertIsNone(data["extracted_text"])

		for file_name, content, error in (
			("data.bin", "x", "Unsupported file type"),
			("blank.txt", "   ", "No readable text"),
		):
			file_doc = _file(file_name=file_name, content=content)
			with self.subTest(file_name), self.assertRaisesRegex(frappe.ValidationError, error):
				load_attachment(file_doc.name)

	def test_only_a_file_the_user_may_read_is_attached(self):
		private = _file(content="secret body")  # Administrator's private file
		frappe.set_user(_ensure_user("attach-other@example.com"))
		with self.assertRaises(frappe.PermissionError):
			load_attachment(private.name)

		own = _file(file_name="mine.txt", content="my own notes")
		data, _file_doc = load_attachment(own.name)
		self.assertEqual(data["extracted_text"], "my own notes")


class TestStageAttachment(IntegrationTestCase):
	def setUp(self):
		self.model = frappe.get_doc(
			{"doctype": "Flow Model", "title": "Stage Model", "model_id": "openai/gpt-4o-mini", "enabled": 1}
		).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_an_image_is_ocred_at_upload_only_for_a_text_only_model(self):
		for model, sees, ocred in (
			(self.model.name, False, True),
			(self.model.name, True, False),
			(None, None, False),
			("no-such-model", None, False),
		):
			with self.subTest(model=model, sees=sees):
				file_doc = _file(file_name="pic.png", content=png_bytes())
				with (
					patch(VISION, return_value=sees),
					patch(f"{MODULE}.extract_file", return_value="OCR") as extract,
				):
					stage_attachment(file_doc.name, model)
				self.assertEqual(extract.call_count, 1 if ocred else 0)
				staged = staged_attachment(file_doc.name)
				if ocred:
					self.assertEqual(staged["ocr_text"], "OCR")
				else:
					self.assertNotIn("ocr_text", staged)

	def test_staging_caches_the_extraction_for_its_user_only(self):
		file_doc = _file(content="staged body")
		chip = stage_attachment(file_doc.name)
		self.assertEqual(set(chip), {"file", "file_name", "file_size"})
		self.assertEqual(chip["file"], file_doc.name)
		self.assertEqual(staged_attachment(file_doc.name)["extracted_text"], "staged body")
		self.assertIsNone(staged_attachment("no-such-file"))

		frappe.set_user(_ensure_user("attach-scope@example.com"))
		self.assertIsNone(staged_attachment(file_doc.name))


class TestBuildTurn(IntegrationTestCase):
	"""How files fold into one turn's message, uploads and attachment rows."""

	def setUp(self):
		# an Error Log outlives the rollback
		self.enterContext(patch("frappe.log_error"))
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
			patch(
				"frappe.flow.knowledge.embedder.embed_texts", side_effect=lambda t: [[1.0, 0, 0, 0]] * len(t)
			)
		)
		self.enterContext(patch("frappe.flow.knowledge.attachment_store.ensure_table"))
		self.index_delete = self.enterContext(patch("frappe.flow.knowledge.attachment_store.delete"))
		self.enterContext(
			patch(
				"frappe.flow.knowledge.retriever.retrieve_attachments", return_value=[{"content": "EXCERPT"}]
			)
		)
		return self.enterContext(patch("frappe.flow.knowledge.attachment_store.add"))

	def test_text_is_inlined_once_with_the_servers_file_marker(self):
		file_doc = _file(file_name="q&a.txt", content="the body")
		turn = build_turn(self.session, "summarize", [file_doc.name, file_doc.name])
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

		with self.assertRaisesRegex(frappe.ValidationError, "at most"):
			build_turn(self.session, "hi", [f"f{i}" for i in range(MAX_ATTACHMENTS + 1)])

	def test_inline_text_is_truncated_to_the_turns_budget(self):
		self.shrink_window(10)  # 20 characters of file text
		with self.subTest("one file"):
			file_doc = _file(file_name="big.txt", content="A" * 30)
			turn = build_turn(self.session, "hi", [file_doc.name])
			self.assertEqual(turn.message, f'hi\n<file name="big.txt">\n{"A" * 20}\n{TRUNCATED}\n</file>')
			self.assertEqual(
				(turn.attachment_rows[0]["mode"], turn.attachment_rows[0]["extracted_text"]),
				("Inline", "A" * 30),
			)
		with self.subTest("files share the budget"):
			first = _file(file_name="first.txt", content="A" * 15)
			second = _file(file_name="second.txt", content="B" * 15)
			turn = build_turn(self.session, "hi", [first.name, second.name])
			self.assertIn(f'<file name="first.txt">\n{"A" * 15}\n</file>', turn.message)
			self.assertIn(f'<file name="second.txt">\n{"B" * 5}\n{TRUNCATED}\n</file>', turn.message)
			self.assertEqual([row["extracted_text"] for row in turn.attachment_rows], ["A" * 15, "B" * 15])

	def test_only_the_largest_files_are_indexed_once_and_excerpted_on_their_turn(self):
		self.shrink_window(10)
		add = self.enable_embeddings()
		large = _file(file_name="large.txt", content="word " * 100)
		small = _file(file_name="small.txt", content="B" * 8)
		turn = build_turn(self.session, "what does it say", [large.name, small.name])
		self.assertEqual([row["mode"] for row in turn.attachment_rows], ["Retrieval", "Inline"])
		self.assertEqual(
			turn.message,
			f"what does it say\n{LARGE_NOTE.format('large.txt')}\n"
			f'<file name="small.txt">\n{"B" * 8}\n</file>\n'
			"Relevant excerpts from the attached files:\n<excerpts>\nEXCERPT\n</excerpts>",
		)
		self.assertEqual(turn.attachment_rows[0]["extracted_text"], ("word " * 100).strip())
		session, key, chunks, vectors = add.call_args.args
		self.assertEqual((session, key, len(chunks), len(vectors)), (self.session.name, large.name, 3, 3))
		self.index_delete.assert_called_once_with(session=self.session.name, attachment=large.name)

		# sending it again reuses its chunks
		self.session.append("attachments", turn.attachment_rows[0])
		add.reset_mock()
		self.index_delete.reset_mock()
		build_turn(self.session, "again", [large.name])
		add.assert_not_called()
		self.index_delete.assert_not_called()

		# a later turn without files searches nothing
		self.session.save(ignore_permissions=True)
		with patch("frappe.flow.knowledge.retriever.retrieve_attachments") as retrieve:
			turn = build_turn(self.session, "and now?", [])
		retrieve.assert_not_called()
		self.assertEqual((turn.message, turn.images, turn.attachment_rows), ("and now?", [], []))

	def test_indexing_and_search_failures_are_surfaced(self):
		self.shrink_window(10)
		self.enable_embeddings()
		for target, error in (
			("frappe.flow.knowledge.embedder.embed_texts", "Could not index"),
			("frappe.flow.knowledge.retriever.retrieve_attachments", "Could not search"),
		):
			with (
				self.subTest(error),
				patch(target, side_effect=RuntimeError("provider down")),
				self.assertRaisesRegex(frappe.ValidationError, error),
			):
				build_turn(self.session, "hi", [_file(file_name="big.txt", content="A" * 30).name])

	def test_an_image_is_sent_to_a_model_that_sees_it_and_ocred_for_one_that_does_not(self):
		data = png_bytes()
		file_doc = _file(file_name="pic.png", content=data)
		for sees in (True, None):  # an unknown model gets images, as on the server
			with self.subTest(sees=sees), patch(VISION, return_value=sees) as vision:
				turn = build_turn(self.session, "what is this", [file_doc.name])
				vision.assert_called_once_with("openai/gpt-4o-mini")
				self.assertEqual(turn.message, "what is this")
				self.assertEqual(turn.images, [("pic.png", data, "image/png")])
				self.assertEqual(turn.attachment_rows[0]["mode"], "Image")
				self.assertNotIn("extracted_text", turn.attachment_rows[0])

		with patch(VISION, return_value=False):
			with patch(f"{MODULE}.extract_file", return_value="OCR TEXT"):
				turn = build_turn(self.session, "read it", [file_doc.name])
			self.assertEqual(turn.message, 'read it\n<file name="pic.png">\nOCR TEXT\n</file>')
			self.assertEqual(turn.images, [])
			self.assertEqual(
				(turn.attachment_rows[0]["mode"], turn.attachment_rows[0]["extracted_text"]),
				("Inline", "OCR TEXT"),
			)
			with (
				patch(f"{MODULE}.extract_file", return_value=""),
				self.assertRaisesRegex(frappe.ValidationError, "No readable text found in pic.png"),
			):
				build_turn(self.session, "read it", [file_doc.name])

	def test_a_staged_image_is_ocred_once_for_whichever_model_needs_it(self):
		# staged for a text-only model: its OCR is reused, and a vision model still gets the image
		ocred = _file(file_name="pic.png", content=png_bytes())
		with (
			patch(VISION, return_value=False),
			patch(f"{MODULE}.extract_file", return_value="OCR TEXT") as extract,
		):
			stage_attachment(ocred.name, self.model.name)
			extract.assert_called_once()
		with patch(f"{MODULE}.extract_file", side_effect=AssertionError("OCR repeated")):
			with patch(VISION, return_value=False):
				text_turn = build_turn(self.session, "read it", [ocred.name])
			with patch(VISION, return_value=True):
				image_turn = build_turn(self.session, "look", [ocred.name])
		self.assertIn("OCR TEXT", text_turn.message)
		self.assertEqual(len(image_turn.images), 1)
		self.assertEqual(image_turn.message, "look")

		# staged for a vision model: OCRed on send to a text-only one
		seen = _file(file_name="seen.png", content=png_bytes())
		with patch(VISION, return_value=True):
			stage_attachment(seen.name, self.model.name)
		with patch(VISION, return_value=False), patch(f"{MODULE}.extract_file", return_value="OCR TEXT"):
			turn = build_turn(self.session, "read it", [seen.name])
		self.assertIn("OCR TEXT", turn.message)
		self.assertEqual(turn.images, [])

	def test_a_file_the_user_may_not_read_is_refused_even_when_staged(self):
		staged = _file(content="staged secret")
		stage_attachment(staged.name)
		with (
			self.subTest("staged, then no longer readable"),
			patch(f"{MODULE}.frappe.has_permission", return_value=False),
			self.assertRaises(frappe.PermissionError),
		):
			build_turn(self.session, "hi", [staged.name])

		private = _file(content="secret body")  # Administrator's private file
		frappe.set_user(_ensure_user("turn-other@example.com"))
		with self.subTest("another user's file"), self.assertRaises(frappe.PermissionError):
			build_turn(self.session, "hi", [private.name])
