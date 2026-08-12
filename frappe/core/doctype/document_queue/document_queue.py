from __future__ import annotations

import importlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, now
from frappe.utils.file_manager import get_file_path
from frappe.utils.task_queue import enqueue_task


class UnsupportedExtractionFile(frappe.ValidationError):
	pass


# Failed is in here on purpose. Extraction falling over doesn't make the upload
# worthless — a reviewer can still open the file and key the document in by hand.
REVIEWABLE_STATUSES = ("Ready for Review", "Failed")

EXTRACTION_METHOD_PDFPLUMBER = "pdfplumber"
EXTRACTION_METHOD_TESSERACT = "tesseract"
EXTRACTION_METHOD_PDFPLUMBER_TESSERACT = "pdfplumber+tesseract"
EXTRACTION_METHOD_UNSUPPORTED = "Unsupported"


class DocumentQueue(Document):

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		created_document: DF.DynamicLink | None
		debug_output: DF.LongText | None
		document_type: DF.Link | None
		error_message: DF.LongText | None
		extracted_text: DF.LongText | None
		extraction_completed_on: DF.Datetime | None
		extraction_method: DF.Data | None
		extraction_started_on: DF.Datetime | None
		raw_extraction_json: DF.JSON | None
		source_file: DF.Attach
		status: DF.Literal["Draft", "Queued", "Processing", "Ready for Review", "Completed", "Failed"]
		task: DF.Link | None

	def validate(self):
		# Label the row now rather than leaving the reason buried in a worker traceback.
		# Extraction still runs and still fails; this just puts "Unsupported" on the form
		# so it's obvious the file type, not the file, is the problem.
		if self.source_file and not (_is_pdf(self.source_file) or _is_image(self.source_file)):
			self.extraction_method = self.extraction_method or EXTRACTION_METHOD_UNSUPPORTED

	def after_insert(self):
		# force=True because there's no "before" to compare against on a fresh row
		self.enqueue_extraction_if_needed(force=True)

	def on_update(self):
		self.enqueue_extraction_if_needed()

	def enqueue_extraction_if_needed(self, *, force: bool = False):
		# after_insert and on_update both fire during a single insert, so the flag keeps
		# one save from queueing the same file twice. skip_auto_extraction is the opt-out
		# for callers that want a row without a worker touching it (see the tests).
		if self.flags.skip_auto_extraction or self.flags.auto_extraction_enqueued or not self.source_file:
			return

		# already in flight, or already finished — leave it alone
		if self.status in {"Queued", "Processing", "Completed"}:
			return

		# Editing anything else on the row shouldn't re-run OCR. Picking a document_type
		# saves the row too, and that's no reason to extract the same file again.
		if not force and not self.has_value_changed("source_file"):
			return

		self.flags.auto_extraction_enqueued = True
		self.enqueue_extraction()

	def enqueue_extraction(self, *, queue: str = "default", enqueue_after_commit: bool = True) -> "Document":
		# Deliberately no reload() here. after_insert/on_update call this halfway through a
		# save, and swapping the whole document out from under the rest of that save breaks
		# it. Callers who need the new status read it back from the database themselves.
		return enqueue_document_extraction(
			self.name, queue=queue, enqueue_after_commit=enqueue_after_commit
		)

	def extract(self) -> dict[str, Any]:
		return extract_document_queue_record(self.name)

	# ---- status transitions ----
	# All of these use update_modified=False. The worker moving a row along isn't a user
	# edit, and bumping `modified` would make a reviewer with the form open hit "Document
	# has been modified after you have opened it" every time a job ran.

	def mark_queued(self, task_name: str | None = None):
		# Clear the last run's output. A re-queued row still showing the previous
		# attempt's text or error reads as though the new run had already finished.
		values = {
			"status": "Queued",
			"extraction_started_on": None,
			"extraction_completed_on": None,
			"extracted_text": None,
			"raw_extraction_json": None,
			"error_message": None,
			"debug_output": None,
		}
		if task_name:
			values["task"] = task_name
		self.db_set(values, update_modified=False)

	def mark_processing(self):
		self.db_set(
			{
				"status": "Processing",
				"extraction_started_on": now(),
				"extraction_completed_on": None,
				"error_message": None,
				"debug_output": None,
			},
			update_modified=False,
		)

	def mark_completed(self, result: dict[str, Any]):
		# "Ready for Review", not "Completed" — the machine is done, but nothing has been
		# produced yet. Completed is reserved for a row that made a real document.
		self.db_set(
			{
				"status": "Ready for Review",
				"extraction_method": result.get("extraction_method"),
				"extraction_completed_on": now(),
				"extracted_text": result.get("extracted_text"),
				"raw_extraction_json": frappe.as_json(result.get("raw_extraction_json")),
				"debug_output": "\n".join(result.get("debug_output") or []),
				"error_message": None,
			},
			update_modified=False,
		)

	def mark_failed(self, error_message: str, debug_output: str | None = None):
		self.db_set(
			{
				"status": "Failed",
				"extraction_completed_on": now(),
				"error_message": error_message,
				"debug_output": debug_output,
			},
			update_modified=False,
		)

	def mark_review_completed(self, document_type: str, document_name: str):
		self.db_set(
			{
				"status": "Completed",
				"document_type": document_type,
				"created_document": document_name,
			},
			update_modified=False,
		)

	def check_target_permission(self, ptype: str = "create", document_type: str | None = None):
		"""Check whether the user is allowed to act on this queue row.

		Nobody creates a Document Queue row by hand — the upload flow creates it for them.
		So "can you edit a queue row" isn't a useful question to ask. We ask the one that
		actually matters instead: can you create the document this row is meant to become?
		If yes, you're allowed to drive it.
		"""
		self.check_permission("read")
		frappe.has_permission(document_type or self.document_type, ptype=ptype, throw=True)

	@frappe.whitelist()
	def extract_in_background(self):
		self.check_target_permission()
		task = self.enqueue_extraction()
		frappe.msgprint(
			_("Queued extraction for {0}.").format(frappe.bold(self.name)),
			indicator="green",
			alert=True,
		)
		return task.name

	@frappe.whitelist()
	def set_document_type(self, document_type: str):
		validate_upload_first_workflow_doctype(document_type)
		# Check the doctype being moved to, not the one being left behind. Otherwise you
		# could point a row you're allowed to touch at one you aren't.
		self.check_target_permission(document_type=document_type)

		self.db_set("document_type", document_type, update_modified=True)
		self.document_type = document_type
		return self.get_document_review_context()

	def get_document_review_context(self):
		return get_document_review_context(self.name)

	@staticmethod
	def clear_old_logs(days=30):
		from frappe.utils import add_days, create_batch, now_datetime

		# delete_doc rather than a straight table delete: each row owns an uploaded file,
		# and a table delete would leave those sitting on disk with nothing pointing at
		# them. Batched with a commit each time so clearing a big backlog doesn't hold
		# one transaction open for the whole run.
		cutoff = add_days(now_datetime(), -cint(days))
		names = frappe.get_all("Document Queue", filters={"creation": ["<", cutoff]}, pluck="name")
		for batch in create_batch(names, 100):
			for name in batch:
				frappe.delete_doc("Document Queue", name, ignore_permissions=True, delete_permanently=True)
			frappe.db.commit()


# ---- the background job ----
# These two stay module-level functions rather than methods. enqueue_task records the
# job as "<module>.<qualname>", and the worker turns that string back into a function
# later by importing everything before the last dot. Nested inside the class, the path
# would gain a "DocumentQueue." segment that isn't an importable module.


def enqueue_document_extraction(
	document_queue: str,
	*,
	queue: str = "default",
	enqueue_after_commit: bool = True,
) -> "Document":
	queue_doc = frappe.get_doc("Document Queue", document_queue)

	task = enqueue_task(
		extract_document_queue_record,
		task_name=_("Extract document {0}").format(queue_doc.name),
		queue=queue,
		ref_doctype="Document Queue",
		ref_docname=queue_doc.name,
		# one live job per row — a double save or an impatient second click on
		# Extract shouldn't start OCR on the same file twice
		job_id=f"document_queue_extract:{queue_doc.name}",
		deduplicate=True,
		enqueue_after_commit=enqueue_after_commit,
		document_queue=queue_doc.name,
	)

	queue_doc.mark_queued(task.name)
	return task


def extract_document_queue_record(document_queue: str) -> dict[str, Any]:
	"""Do the actual extraction. This is what the background worker runs."""
	queue_doc = frappe.get_doc("Document Queue", document_queue)
	queue_doc.mark_processing()
	# Commit before the slow part. Extraction can run for minutes, and until this
	# lands the row still reads "Queued" to anyone watching the form.
	frappe.db.commit()  # nosemgrep

	try:
		file_path = get_file_path(queue_doc.source_file)
		result = extract_file(file_path)
		queue_doc.mark_completed(result)
		return result
	except Exception as exc:
		frappe.db.rollback()
		# some exceptions carry no message at all, and "Failed: " with nothing after
		# it tells a reviewer nothing — fall back to the class name
		error_message = str(exc) or exc.__class__.__name__
		# the rollback just threw away this doc's uncommitted state, so fetch the row
		# again before writing the failure onto it
		queue_doc = frappe.get_doc("Document Queue", document_queue)
		queue_doc.mark_failed(error_message, frappe.get_traceback(with_context=True))
		# Re-raising hands the error up to the worker, which rolls back again. Commit
		# first or the row sits on "Processing" forever with nothing coming to move it.
		frappe.db.commit()  # nosemgrep
		raise


@frappe.whitelist()
def get_ready_for_review_count(document_type: str) -> int:
	if not is_upload_first_workflow_doctype(document_type):
		return 0

	# Count in the database instead of fetching rows and len()-ing them. This fires on
	# every list-view render and the backlog it counts has no ceiling. get_list rather
	# than db.count so get_permission_query_conditions below still filters the rows —
	# db.count would happily count rows the user can't see.
	result = frappe.get_list(
		"Document Queue",
		filters={
			"document_type": document_type,
			"status": "Ready for Review",
		},
		fields=[{"COUNT": "*"}],
		as_list=True,
	)
	return cint(result[0][0]) if result else 0


@frappe.whitelist()
def create_upload_first_queue(file_name: str, document_type: str) -> dict[str, Any]:
	validate_upload_first_workflow_doctype(document_type)
	# Nobody has create rights on Document Queue, so this inserts the row on the user's
	# behalf with ignore_permissions below. Being allowed to create the target document
	# is what earns them that — check it before, not after.
	frappe.has_permission(document_type, ptype="create", throw=True)

	file_doc = frappe.get_doc("File", file_name)
	file_doc.check_permission("read")
	# write too, because we're about to re-parent this file onto the queue row — that's
	# a change to the File, and passing a file you can only read shouldn't let you do it
	file_doc.check_permission("write")

	queue_doc = frappe.get_doc(
		{
			"doctype": "Document Queue",
			"source_file": file_doc.file_url,
			"document_type": document_type,
		}
	)
	queue_doc.insert(ignore_permissions=True)

	# Hang the file off the queue row. Until a real document exists, this row is the only
	# thing that owns the upload — which is what makes deleting the row take the file with
	# it, and what gives the File somewhere to resolve its permissions from.
	# link_to_document moves the attachment on once there's a better owner for it.
	file_doc.db_set(
		{
			"attached_to_doctype": queue_doc.doctype,
			"attached_to_name": queue_doc.name,
			"attached_to_field": "source_file",
		},
		update_modified=False,
	)

	return get_document_review_context(queue_doc.name)


@frappe.whitelist()
def get_document_review_context(document_queue: str) -> dict[str, Any]:
	queue_doc = frappe.get_doc("Document Queue", document_queue)
	queue_doc.check_permission("read")

	return {
		"queue_name": queue_doc.name,
		"task_id": queue_doc.task,
		"status": queue_doc.status,
		"document_type": queue_doc.document_type,
		"created_document": queue_doc.created_document,
		"source_file": queue_doc.source_file,
		"source_file_url": _get_source_file_preview_url(queue_doc),
		# The one-line reason is the whole point of a Failed row for a reviewer, so it
		# always goes out. This is the safe half of the failure; the traceback is below.
		"error_message": queue_doc.error_message or "",
		"extracted_text": queue_doc.extracted_text or "",
		# Every word box on every page — big, and only ever drawn in the developer-mode
		# debug tab. No reason to put it on the wire for everyone else.
		"raw_extraction_json": (
			_parse_json(queue_doc.raw_extraction_json) if frappe.conf.developer_mode else {}
		),
		# Being able to read the row doesn't mean you get to read its traceback. Ask the
		# same permlevel the field itself carries, so this endpoint and /api/resource
		# don't disagree about who's allowed to see it.
		"debug_output": (
			queue_doc.debug_output or ""
			if queue_doc.has_permlevel_access_to("debug_output", permission_type="read")
			else ""
		),
	}


@frappe.whitelist()
def link_to_document(document_queue: str, document_type: str, document_name: str) -> dict[str, Any]:
	queue_doc = frappe.get_doc("Document Queue", document_queue)
	queue_doc.check_permission("read")

	# The row decides what it becomes, not the caller. If we just used whatever doctype
	# was passed in, this would quietly re-target the row and skip set_document_type —
	# which is where the upload-first and permission checks live.
	if document_type != queue_doc.document_type:
		frappe.throw(
			_("Document Queue {0} is for {1}, not {2}.").format(
				frappe.bold(queue_doc.name),
				frappe.bold(_(queue_doc.document_type)),
				frappe.bold(_(document_type)),
			)
		)

	# Linking a second time would strand the first document's attachment. By then the
	# file has already moved off the queue row, so the lookup in
	# attach_source_file_to_document finds nothing and the second document silently
	# ends up with no file at all.
	if queue_doc.status not in REVIEWABLE_STATUSES:
		frappe.throw(
			_("Document Queue {0} is {1} and cannot be linked again.").format(
				frappe.bold(queue_doc.name), frappe.bold(_(queue_doc.status))
			)
		)

	if not frappe.db.exists(document_type, document_name):
		frappe.throw(
			_("Document {0} {1} does not exist.").format(
				frappe.bold(document_type), frappe.bold(document_name)
			)
		)

	target_doc = frappe.get_doc(document_type, document_name)
	# write, not read — we're about to attach a file to this document
	target_doc.check_permission("write")
	queue_doc.mark_review_completed(target_doc.doctype, target_doc.name)
	attach_source_file_to_document(queue_doc, target_doc)

	return {
		"ok": True,
		"status": queue_doc.status,
		"document_type": queue_doc.document_type,
		"created_document": queue_doc.created_document,
	}


def attach_source_file_to_document(queue_doc: DocumentQueue, target_doc: Document):
	"""Hand the uploaded file over from the queue row to the document it produced.

	The file follows the document from here on. The row keeps pointing at the same
	file_url so the review screen still has something to show, but the queue row is no
	longer what owns it — so clearing old queue rows won't take the file with it.
	"""
	file_doc_name = frappe.db.get_value(
		"File",
		{
			"file_url": queue_doc.source_file,
			"attached_to_doctype": queue_doc.doctype,
			"attached_to_name": queue_doc.name,
		},
		"name",
	)
	# No File row means the upload came in some other way — a URL typed straight into
	# source_file, say. Nothing to move, and no reason to fail the link over it.
	if not file_doc_name:
		return

	file_doc = frappe.get_doc("File", file_doc_name)
	file_doc.db_set(
		{
			"attached_to_doctype": target_doc.doctype,
			"attached_to_name": target_doc.name,
			# cleared because source_file is a field on the queue row, not on the
			# target — leaving it set would point at a field the document hasn't got
			"attached_to_field": None,
		},
		update_modified=False,
	)


def validate_upload_first_workflow_doctype(document_type: str):
	if not frappe.db.exists("DocType", document_type):
		frappe.throw(_("DocType {0} does not exist.").format(frappe.bold(document_type)))

	if not is_upload_first_workflow_doctype(document_type):
		frappe.throw(
			_("{0} does not have Upload First Workflow enabled.").format(frappe.bold(document_type)),
			frappe.ValidationError,
		)


def is_upload_first_workflow_doctype(document_type: str) -> bool:
	if not document_type:
		return False

	values = frappe.db.get_value(
		"DocType",
		document_type,
		["enable_upload_first_workflow", "istable"],
		as_dict=True,
	)
	# istable rules out child tables. A child row can't exist on its own, so there'd be
	# nothing for a reviewer to open and no document for the row to become.
	return bool(values and cint(values.enable_upload_first_workflow) and not cint(values.istable))


# ---- pulling text out of the file ----
# Two routes in. A PDF usually carries a real text layer, so pdfplumber reads it
# straight off and OCR is only the fallback. An image has no text layer at all, so
# tesseract is the only option. Both return the same shape so the caller doesn't care
# which one ran.


def extract_file(file_path: str) -> dict[str, Any]:
	if _is_image(file_path):
		return extract_image(file_path)

	if _is_pdf(file_path):
		return extract_pdf(file_path)

	raise UnsupportedExtractionFile(_("Only PDF and image extraction is supported for Document Queue"))


def extract_image(file_path: str) -> dict[str, Any]:
	text, words, debug_output = extract_image_text_with_tesseract(file_path)
	# Hard failure here, unlike the PDF path. There tesseract is a fallback and losing it
	# just means a thinner result; here it was the only way to read the file at all.
	if not text:
		raise UnsupportedExtractionFile(_("Tesseract is required to extract text from images"))

	return {
		"extraction_method": EXTRACTION_METHOD_TESSERACT,
		"extracted_text": text,
		"raw_extraction_json": {
			"file": Path(file_path).name,
			"extraction_method": EXTRACTION_METHOD_TESSERACT,
			"pages": [
				{
					"page_number": 1,
					"text": text,
					"words": words,
					"tables": [],
				}
			],
		},
		"debug_output": debug_output,
	}


def extract_pdf(file_path: str) -> dict[str, Any]:
	pdfplumber = _get_pdfplumber()
	pages = []
	text_parts = []
	layout_text_parts = []
	debug_output = []

	with pdfplumber.open(file_path) as pdf:
		for page_number, page in enumerate(pdf.pages, start=1):
			text = page.extract_text() or ""
			# layout=True keeps the original spacing, which is what makes an invoice
			# still look like a table instead of one long run of words
			layout_text = page.extract_text(layout=True) or ""
			# words carry coordinates — the review screen draws boxes over the preview
			# from these, so they're kept even though the text above covers reading
			words = page.extract_words(x_tolerance=1, y_tolerance=3) or []
			tables = page.extract_tables() or []

			text_parts.append(text)
			layout_text_parts.append(layout_text)
			pages.append(
				{
					"page_number": page_number,
					"width": page.width,
					"height": page.height,
					"text": text,
					"layout_text": layout_text,
					"words": _json_safe(words),
					"tables": _json_safe(tables),
				}
			)

	extracted_text = "\n\n".join(part for part in text_parts if part).strip()
	extracted_layout_text = "\n\n".join(part for part in layout_text_parts if part).strip()
	# prefer the spaced-out version, fall back to the plain one if layout mode came back
	# with nothing (it can, on pages with odd or missing font metrics)
	cleaned_text = extracted_layout_text or extracted_text
	extraction_method = EXTRACTION_METHOD_PDFPLUMBER
	ocr_text = None

	# Nothing worth reading came off the text layer, so this is probably a scan. Fall
	# back to OCR — but keep the pdfplumber pages either way, since the word boxes on
	# them are still what the review screen draws with.
	if not _is_useful_text(cleaned_text):
		ocr_text, ocr_debug = extract_pdf_text_with_tesseract(file_path)
		debug_output.extend(ocr_debug)
		# still nothing? leave the thin pdfplumber text in place rather than blanking it
		if ocr_text:
			extraction_method = EXTRACTION_METHOD_PDFPLUMBER_TESSERACT
			cleaned_text = ocr_text

	raw = {
		"file": Path(file_path).name,
		"extraction_method": extraction_method,
		"pages": pages,
	}
	if ocr_text:
		raw["ocr_text"] = ocr_text

	return {
		"extraction_method": extraction_method,
		"extracted_text": cleaned_text,
		"raw_extraction_json": raw,
		"debug_output": debug_output,
	}


def _run_ocr_command(command: list[str], **kwargs) -> subprocess.CompletedProcess:
	"""Run one of the OCR binaries, putting its stderr in the error if it fails.

	Without this you get "returned non-zero exit status 1" on the queue row, which tells
	whoever is looking at it nothing. Tesseract's own message usually says exactly what
	was wrong with the file.
	"""
	completed = subprocess.run(command, capture_output=True, **kwargs)
	if completed.returncode != 0:
		stderr = completed.stderr
		if isinstance(stderr, bytes):
			stderr = stderr.decode(errors="replace")
		raise RuntimeError(f"{command[0]} failed: {(stderr or '').strip()}")
	return completed


def extract_pdf_text_with_tesseract(file_path: str) -> tuple[str | None, list[str]]:
	debug_output = []
	pdftoppm = shutil.which("pdftoppm")
	tesseract = shutil.which("tesseract")

	# Both are system packages, not Python ones, so a site can easily be missing them.
	# Say so in the debug output and give up quietly — the caller still has whatever
	# pdfplumber managed, and a missing optional tool isn't the upload's fault.
	if not pdftoppm or not tesseract:
		debug_output.append("OCR skipped: pdftoppm or tesseract is not available.")
		return None, debug_output

	# tesseract reads images, not PDFs, so each page becomes a PNG first. 200 dpi is the
	# usual floor for readable OCR; lower loses small print, higher mostly costs time.
	with tempfile.TemporaryDirectory() as tmpdir:
		prefix = str(Path(tmpdir) / "page")
		_run_ocr_command([pdftoppm, "-png", "-r", "200", file_path, prefix])

		ocr_parts = []
		# sorted() because glob order isn't guaranteed, and unsorted pages would
		# scramble a multi-page document into nonsense
		for image_path in sorted(Path(tmpdir).glob("page-*.png")):
			completed = _run_ocr_command([tesseract, str(image_path), "stdout"], text=True)
			ocr_parts.append(completed.stdout.strip())

	return "\n\n".join(part for part in ocr_parts if part).strip() or None, debug_output


def extract_image_text_with_tesseract(file_path: str) -> tuple[str | None, list[dict[str, Any]], list[str]]:
	debug_output = []
	tesseract = shutil.which("tesseract")

	if not tesseract:
		debug_output.append("Image OCR skipped: tesseract is not available.")
		return None, [], debug_output

	# Two passes over the same image: plain text to read, then tsv for the coordinates.
	# tesseract won't emit both at once, and the tsv text column alone doesn't rebuild
	# into properly spaced lines.
	text_completed = _run_ocr_command([tesseract, file_path, "stdout"], text=True)
	tsv_completed = _run_ocr_command([tesseract, file_path, "stdout", "tsv"], text=True)

	return (
		text_completed.stdout.strip() or None,
		_parse_tesseract_tsv_words(tsv_completed.stdout),
		debug_output,
	)


def _get_pdfplumber():
	# Imported here rather than at the top of the file so that a site without pdfplumber
	# installed still loads this module — image extraction and the whole review flow work
	# without it, and only PDFs hit this path.
	try:
		return importlib.import_module("pdfplumber")
	except ImportError:
		frappe.throw(
			_("pdfplumber is required to extract PDF text. Please install project dependencies."),
			frappe.ValidationError,
		)


def _is_pdf(path_or_url: str) -> bool:
	# split on "?" because these take file URLs too, and a private file's URL carries a
	# ?fid= query string that would otherwise hide the extension
	return path_or_url.lower().split("?", 1)[0].endswith(".pdf")


def _is_image(path_or_url: str) -> bool:
	return Path(path_or_url.lower().split("?", 1)[0]).suffix in {
		".bmp",
		".gif",
		".jpeg",
		".jpg",
		".png",
		".tif",
		".tiff",
		".webp",
	}


# Is there enough here to believe the PDF really had a text layer?
#
# A scanned page still returns a few stray characters from pdfplumber — a header, a
# stamp, junk from an embedded logo. A genuine text layer returns far more than 20
# characters. So anything this short is treated as "no text layer, go and OCR it"
# rather than accepted as the extraction result.
def _is_useful_text(text: str | None) -> bool:
	return bool(text and len(text.strip()) >= 20)


def _parse_json(value: str | dict | list | None):
	if not value:
		return {}
	if isinstance(value, (dict, list)):
		return value
	try:
		return json.loads(value)
	except Exception:
		# This only feeds a debug panel. Unreadable stored JSON isn't worth failing the
		# whole review screen over — show nothing in that tab and carry on.
		return {}


def _get_source_file_preview_url(queue_doc: DocumentQueue) -> str:
	file_doc_name = frappe.db.get_value(
		"File",
		{
			"file_url": queue_doc.source_file,
			"attached_to_doctype": queue_doc.doctype,
			"attached_to_name": queue_doc.name,
		},
		"name",
	)

	if not file_doc_name:
		return queue_doc.source_file

	# unique_url tacks the file's id onto a private file's URL, which lets the permission
	# check on the way back skip hunting for which File this even is. Matters here
	# because the review screen loads the preview on every open.
	file_doc = frappe.get_doc("File", file_doc_name)
	return file_doc.unique_url


def _json_safe(value):
	# pdfplumber hands back Decimals for every coordinate, which json.dumps refuses on
	# its own. default=str turns those (and anything else exotic) into strings so the
	# result survives being stored in the row's JSON field.
	return json.loads(json.dumps(value, default=str))


def _parse_tesseract_tsv_words(tsv: str) -> list[dict[str, Any]]:
	"""Turn tesseract's tsv output into the same word shape pdfplumber gives us.

	Both extraction routes have to agree on this, because the review screen draws its
	boxes from these dicts and shouldn't care which tool produced the page.
	"""
	lines = [line for line in (tsv or "").splitlines() if line.strip()]
	# a header row on its own means tesseract found no words
	if len(lines) <= 1:
		return []

	headers = lines[0].split("\t")
	words = []
	for line in lines[1:]:
		values = line.split("\t")
		# strict=False because tesseract drops trailing empty columns on some rows;
		# a short row should lose its last field, not blow up the whole page
		row = dict(zip(headers, values, strict=False))
		text = (row.get("text") or "").strip()
		# tesseract emits a row per layout block too — page, paragraph, line — and those
		# carry no text. They'd become invisible zero-content boxes on the preview.
		if not text:
			continue

		# tsv gives position and size; pdfplumber gives two corners. Convert, so the
		# review screen has one shape to draw rather than two.
		left = cint(row.get("left"))
		top = cint(row.get("top"))
		width = cint(row.get("width"))
		height = cint(row.get("height"))
		words.append(
			{
				"text": text,
				"x0": left,
				"top": top,
				"x1": left + width,
				"bottom": top + height,
				"confidence": row.get("conf"),
			}
		)

	return words


# ---- who can see a queue row ----
# Both of these are wired up in hooks.py. They answer the same question at two different
# moments: has_permission when someone opens one row, get_permission_query_conditions
# when someone lists many. The answer in both cases is "whatever the target doctype
# says" — a queue row for a Sales Invoice should be no easier to reach than the invoice.


def has_permission(doc, ptype="read", user=None):
	# Worth knowing: this hook can only take permission away, never hand it out. Frappe
	# still checks Document Queue's own DocPerms first and only then asks us (see
	# has_controller_permissions), so returning True here doesn't let anyone in — it just
	# declines to narrow things further.
	if not doc or not getattr(doc, "document_type", None):
		# No target yet, so there's nothing to mirror. document_type is mandatory, so the
		# only rows in this state are half-built ones; they stay on Document Queue's own
		# owner-scoped rules, which already keep them to whoever uploaded the file.
		return True

	return frappe.has_permission(doc.document_type, ptype=ptype, user=user)


def get_permission_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user

	# no filter at all — Administrator sees the whole queue
	if user == "Administrator":
		return ""

	from frappe.permissions import get_doctypes_with_read

	readable_doctypes = ", ".join(frappe.db.escape(dt) for dt in get_doctypes_with_read(user))

	# A user who can read nothing must see nothing. Returning "" here would read as "no
	# filter needed" and show them every row in the queue, so say false out loud instead.
	if not readable_doctypes:
		return "1=0"

	return f"`tabDocument Queue`.`document_type` IN ({readable_doctypes})"
