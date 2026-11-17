# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import io
from unittest.mock import patch

from PIL import Image

import frappe
from frappe.flow.doctype.flow_session_attachment.flow_session_attachment import (
	MAX_ATTACHMENTS,
	PASTE_LIMIT,
	READ_CHAR_LIMIT,
	TRUNCATED,
	_size_text,
	build_turn,
	hold_sent_files,
	load_attachment,
	read_attachment,
	release_sent_files,
	stage_attachment,
	staged_attachment,
)
from frappe.tests import IntegrationTestCase

MODULE = "frappe.flow.doctype.flow_session_attachment.flow_session_attachment"
VISION = "flow_harness.model.catalog.model_supports_images"


def block(file_doc, body: str) -> str:
	return (
		f'<file name="{file_doc.file_name.replace("&", "&amp;")}" file="{file_doc.name}" '
		f'url="{file_doc.file_url.replace("&", "&amp;")}" size="{_size_text(file_doc.file_size)}">'
		f"\n{body}\n</file>"
	)


def prose_preview(text: str, more: bool = False) -> str:
	lines = text.count("\n") + 1
	note = " Read more with read_attachment." if more else ""
	return (
		f"Saved as a File, not shown in full: {len(text):,} characters, {lines:,} lines.\n"
		f"{text[:1000]}\n[Preview: the first {min(1000, len(text)):,} characters.{note}]"
	)


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
		self.assertEqual(turn.message, f"summarize\n{block(file_doc, 'the body')}")
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

	def test_without_read_attachment_text_over_the_budget_is_truncated_smallest_files_first(self):
		self.shrink_window(10)  # 20 characters of file text
		with self.subTest("one file"):
			file_doc = _file(file_name="big.txt", content="A" * 30)
			turn = build_turn(self.session, "hi", [file_doc.name])
			self.assertEqual(turn.message, f"hi\n{block(file_doc, 'A' * 20 + chr(10) + TRUNCATED)}")
			self.assertEqual(
				(turn.attachment_rows[0]["mode"], turn.attachment_rows[0]["extracted_text"]),
				("Inline", "A" * 30),
			)
		with self.subTest("files share the budget"):
			larger = _file(file_name="larger.txt", content="A" * 16)
			smaller = _file(file_name="smaller.txt", content="B" * 15)
			turn = build_turn(self.session, "hi", [larger.name, smaller.name])
			self.assertEqual(
				turn.message,
				f"hi\n{block(larger, 'A' * 5 + chr(10) + TRUNCATED)}\n{block(smaller, 'B' * 15)}",
			)
			self.assertEqual([row["extracted_text"] for row in turn.attachment_rows], ["A" * 16, "B" * 15])

	def test_an_agent_that_reads_attachments_pastes_prose_up_to_the_limit_and_previews_tables(self):
		self.give_read_attachment()
		note = _file(file_name="note.txt", content="N" * (PASTE_LIMIT - 100))
		long = _file(file_name="long.txt", content="L" * (PASTE_LIMIT + 1))
		rows = "\n".join(f"{i},site{i}.example.com" for i in range(1, 400))
		table = _file(file_name="events.csv", content=f'name,site\n{rows}\n9,"two\nlines"\n')
		turn = build_turn(self.session, "import this", [note.name, long.name, table.name])
		preview = "\n".join(
			[
				"Saved as a File, not shown in full. To import it, pass its url to Data Import's import_file.",
				"Table: 400 rows, columns: name, site",
				"name,site",
				*rows.split("\n")[:5],
				"[Preview: the header and the first 5 rows. Read more with read_attachment.]",
			]
		)
		self.assertEqual(
			turn.message,
			f"import this\n{block(note, 'N' * (PASTE_LIMIT - 100))}"
			f"\n{block(long, prose_preview('L' * (PASTE_LIMIT + 1), more=True))}"
			f"\n{block(table, preview)}",
		)
		self.assertEqual([row["mode"] for row in turn.attachment_rows], ["Inline"] * 3)

		# a table small enough to read whole is pasted
		text = "name\n" + "\n".join(["x"] * 100)
		small = _file(file_name="small.csv", content=text)
		turn = build_turn(self.session, "import this", [small.name])
		self.assertEqual(turn.message, f"import this\n{block(small, text)}")

	def test_an_xlsx_is_previewed_as_data_import_reads_it(self):
		from frappe.utils.xlsxutils import make_xlsx

		self.give_read_attachment()
		content = make_xlsx([["item", "qty"], ["Pen", 2], [None, None], ["Ink", None]], "Sheet").getvalue()
		file_doc = _file(file_name="stock.xlsx", content=content)
		with patch(f"{MODULE}.PASTE_LIMIT", 0):
			turn = build_turn(self.session, "import", [file_doc.name])
		self.assertIn(
			"active sheet, which Data Import reads): 2 rows, columns: item, qty\nitem,qty\nPen,2\nInk,\n",
			turn.message,
		)
		# pasted, it keeps its columns too
		turn = build_turn(self.session, "import", [file_doc.name])
		self.assertEqual(
			turn.message, f"import\n{block(file_doc, 'item,qty' + chr(10) + 'Pen,2' + chr(10) + 'Ink,')}"
		)

	def test_a_table_data_import_cannot_take_or_cannot_parse_says_so(self):
		self.give_read_attachment()
		with patch(f"{MODULE}.PASTE_LIMIT", 0):
			tsv = _file(file_name="stock.tsv", content="item\tqty\nPen\t2\n")
			self.assertNotIn("Data Import", build_turn(self.session, "hi", [tsv.name]).message)
			broken = _file(file_name="broken.csv", content="a,b\n" + "x" * 140000 + "\n")
			with patch("frappe.msgprint"):
				message = build_turn(self.session, "hi", [broken.name]).message
			self.assertIn("Saved as a File, not shown in full: 140,004 characters", message)

	def give_read_attachment(self):
		from frappe.flow.tools.builtins import sync_builtin_tools

		sync_builtin_tools()
		agent = frappe.get_doc("Flow Agent", self.session.agent)
		agent.append("tools", {"tool": "frappe/read_attachment"})
		agent.save()

	def test_only_the_largest_files_are_indexed_once_and_excerpted_on_their_turn(self):
		self.shrink_window(10)
		add = self.enable_embeddings()
		large = _file(file_name="large.txt", content="word " * 100)
		small = _file(file_name="small.txt", content="B" * 8)
		turn = build_turn(self.session, "what does it say", [large.name, small.name])
		self.assertEqual([row["mode"] for row in turn.attachment_rows], ["Retrieval", "Inline"])
		self.assertEqual(
			turn.message,
			f"what does it say\n{block(large, prose_preview(('word ' * 100).strip()))}\n"
			f"{block(small, 'B' * 8)}\n"
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
			self.assertEqual(turn.message, f"read it\n{block(file_doc, 'OCR TEXT')}")
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


class TestReadAttachment(IntegrationTestCase):
	"""What `read_attachment` returns, and which Files it reads."""

	def setUp(self):
		self.user = _ensure_user("attach-reader@example.com")
		frappe.set_user(self.user)
		model = frappe.get_doc(
			{"doctype": "Flow Model", "title": "Read Model", "model_id": "openai/gpt-4o-mini", "enabled": 1}
		).insert(ignore_permissions=True)
		agent = frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Read Agent",
				"model": model.name,
				"instructions": "x",
				"enabled": 1,
			}
		).insert(ignore_permissions=True)
		self.session = frappe.get_doc({"doctype": "Flow Session", "agent": agent.name}).insert(
			ignore_permissions=True
		)

	def tearDown(self):
		release_sent_files(self.session.name)
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def attached(self, file_name="notes.txt", content="one\ntwo\nthree", session=None):
		return _file(
			file_name=file_name,
			content=content,
			attached_to_doctype="Flow Session",
			attached_to_name=session or self.session.name,
		)

	def test_lines_are_read_in_ranges_and_capped_in_characters(self):
		file_doc = self.attached()
		read = lambda *args: read_attachment(self.session.name, file_doc.name, *args)  # noqa: E731
		self.assertEqual(read(), "one\ntwo\nthree\n[Lines 1-3 of 3.]")
		self.assertEqual(read(2, 1), "two\n[Lines 2-2 of 3. Continue at offset 3.]")
		self.assertEqual(read_attachment(self.session.name, "notes.txt", 3), "three\n[Lines 3-3 of 3.]")

		self.assertEqual(read(9), "[Past the end: 3 lines.]")

		long = self.attached("long.json", "x" * (READ_CHAR_LIMIT + 50) + "\nend")
		result = read_attachment(self.session.name, long.name)
		self.assertEqual(result, "x" * READ_CHAR_LIMIT + "\n[Lines 1-1 of 3. Continue at offset 2.]")
		self.assertEqual(
			read_attachment(self.session.name, long.name, 2), "x" * 50 + "\nend\n[Lines 2-3 of 3.]"
		)

		table = self.attached("events.csv", 'name,note\n1,"two\nlines"\n2,b\n')
		self.assertEqual(
			read_attachment(self.session.name, table.name, 2, 1),
			'1,"two\nlines"\n[Lines 2-2 of 3. Continue at offset 3.]',
		)

	def test_without_a_file_it_lists_the_sessions_files(self):
		file_doc = self.attached()
		self.attached(session=frappe.generate_hash(length=10))
		self.assertEqual(
			read_attachment(self.session.name, None),
			[{"file": file_doc.name, "file_name": "notes.txt", "url": file_doc.file_url}],
		)

	def test_only_files_of_this_session_the_user_may_read(self):
		elsewhere = _file(attached_to_doctype="ToDo", attached_to_name="x")
		other_session = self.attached(session=frappe.generate_hash(length=10))
		loose = _file()
		for file_doc in (elsewhere, other_session, loose):
			with self.subTest(file_doc.attached_to_doctype), self.assertRaises(frappe.PermissionError):
				read_attachment(self.session.name, file_doc.name)

		frappe.set_user("Administrator")
		private = self.attached(content="admin only")
		frappe.set_user(self.user)
		with self.assertRaises(frappe.PermissionError):
			read_attachment(self.session.name, private.name)

	def test_a_file_being_sent_is_readable_before_its_claim_commits(self):
		loose = _file(content="first turn")
		hold_sent_files(self.session.name, [loose.name])
		self.assertEqual(read_attachment(self.session.name, loose.name), "first turn\n[Lines 1-1 of 1.]")
		self.assertEqual([row["file"] for row in read_attachment(self.session.name, None)], [loose.name])
		self.assertEqual(read_attachment(self.session.name, "note.txt"), "first turn\n[Lines 1-1 of 1.]")
		release_sent_files(self.session.name)
		with self.assertRaises(frappe.PermissionError):
			read_attachment(self.session.name, loose.name)
