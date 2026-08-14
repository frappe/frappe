from __future__ import annotations

import importlib
import json
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
EXTRACTION_METHOD_PREVIEW_ONLY = "Preview Only"
EXTRACTION_METHOD_UNSUPPORTED = "Unsupported"


class AttachmentQueue(Document):
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

		# already in flight, or already finished
		if self.status in {"Queued", "Processing", "Completed"}:
			return

		# Editing anything else on the row shouldn't re-run extraction. Picking a document_type
		# saves the row too, and that's no reason to extract the same file again.
		if not force and not self.has_value_changed("source_file"):
			return

		self.flags.auto_extraction_enqueued = True
		self.enqueue_extraction()

	def enqueue_extraction(self, *, queue: str = "default", enqueue_after_commit: bool = True) -> "Document":
		# Deliberately no reload() here. after_insert/on_update call this halfway through a
		# save, and swapping the whole document out from under the rest of that save breaks
		# it. Callers who need the new status read it back from the database themselves.
		return enqueue_document_extraction(self.name, queue=queue, enqueue_after_commit=enqueue_after_commit)

	def extract(self) -> dict[str, Any]:
		return extract_attachment_queue_record(self.name)

	def mark_queued(self, task_name: str | None = None):
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
		"""Authorise an action that drives this queue row.

		Queue rows are framework-owned records, like Email Queue or Background Task:
		users never author them. Reading one is scoped to its owner by the DocType's `if_owner` rule;
		anything that drives it is authorised against the *target* DocType, because
		the row exists only to produce a document of that type.
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
		# Authorise against the DocType being re-targeted to.
		self.check_target_permission(document_type=document_type)

		self.db_set("document_type", document_type, update_modified=True)
		self.document_type = document_type
		return self.get_document_review_context()

	def get_document_review_context(self):
		return get_document_review_context(self.name)

	@staticmethod
	def clear_old_logs(days=30):
		from frappe.utils import add_days, create_batch, now_datetime

		# Route through delete_doc (not a raw table delete) so attached source files
		# are cleaned up too, instead of being orphaned on disk. Batched, with a commit
		# per batch, so a large backlog doesn't run as one long-held transaction.
		cutoff = add_days(now_datetime(), -cint(days))
		names = frappe.get_all("Attachment Queue", filters={"creation": ["<", cutoff]}, pluck="name")
		for batch in create_batch(names, 100):
			for name in batch:
				frappe.delete_doc("Attachment Queue", name, ignore_permissions=True, delete_permanently=True)
			frappe.db.commit()


# ---- the background job ----
# These two stay module-level functions rather than methods. enqueue_task records the
# job as "<module>.<qualname>", and the worker turns that string back into a function
# later by importing everything before the last dot.


def enqueue_document_extraction(
	attachment_queue: str,
	*,
	queue: str = "default",
	enqueue_after_commit: bool = True,
) -> "Document":
	queue_doc = frappe.get_doc("Attachment Queue", attachment_queue)

	task = enqueue_task(
		extract_attachment_queue_record,
		task_name=_("Extract document {0}").format(queue_doc.name),
		queue=queue,
		ref_doctype="Attachment Queue",
		ref_docname=queue_doc.name,
		# one live job per row — a double save or an impatient second click on
		# Extract shouldn't extract the same file twice
		job_id=f"attachment_queue_extract:{queue_doc.name}",
		deduplicate=True,
		enqueue_after_commit=enqueue_after_commit,
		attachment_queue=queue_doc.name,
	)

	queue_doc.mark_queued(task.name)
	return task


def extract_attachment_queue_record(attachment_queue: str) -> dict[str, Any]:
	"""Do the actual extraction. This is what the background worker runs."""
	queue_doc = frappe.get_doc("Attachment Queue", attachment_queue)
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
		queue_doc = frappe.get_doc("Attachment Queue", attachment_queue)
		queue_doc.mark_failed(error_message, frappe.get_traceback(with_context=True))
		# Re-raising hands the error up to the worker, which rolls back again. Commit
		# first or the row sits on "Processing" forever with nothing coming to move it.
		frappe.db.commit()  # nosemgrep
		raise


@frappe.whitelist()
def get_ready_for_review_count(document_type: str) -> int:
	if not is_upload_first_workflow_doctype(document_type):
		return 0

	# Counted in the database rather than by fetching every row: this runs on every
	# list-view render, and the backlog it counts is unbounded. get_list (not db.count)
	# so the permission query conditions and owner scoping still apply.
	result = frappe.get_list(
		"Attachment Queue",
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
	# Users hold no create right on Attachment Queue itself, so the row is inserted on their behalf.
	# Being allowed to create the target document is what authorises that.
	frappe.has_permission(document_type, ptype="create", throw=True)

	file_doc = frappe.get_doc("File", file_name)
	file_doc.check_permission("read")
	file_doc.check_permission("write")

	queue_doc = frappe.get_doc(
		{
			"doctype": "Attachment Queue",
			"source_file": file_doc.file_url,
			"document_type": document_type,
		}
	)
	queue_doc.insert(ignore_permissions=True)

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
def get_document_review_context(attachment_queue: str) -> dict[str, Any]:
	queue_doc = frappe.get_doc("Attachment Queue", attachment_queue)
	queue_doc.check_permission("read")

	return {
		"queue_name": queue_doc.name,
		"task_id": queue_doc.task,
		"status": queue_doc.status,
		"document_type": queue_doc.document_type,
		"created_document": queue_doc.created_document,
		"source_file": queue_doc.source_file,
		"source_file_url": _get_source_file_preview_url(queue_doc),
		"error_message": queue_doc.error_message or "",
		"extracted_text": queue_doc.extracted_text or "",
		# Every word box on every page, and only ever rendered in the developer-mode
		# debug tab — not worth putting on the wire for everyone else.
		"raw_extraction_json": (
			_parse_json(queue_doc.raw_extraction_json) if frappe.conf.developer_mode else {}
		),
		# Reading the queue row does not earn you its traceback. Ask the same permlevel
		# the field carries, so this method and /api/resource agree on who sees it.
		"debug_output": (
			queue_doc.debug_output or ""
			if queue_doc.has_permlevel_access_to("debug_output", permission_type="read")
			else ""
		),
	}


@frappe.whitelist()
def link_to_document(attachment_queue: str, document_type: str, document_name: str) -> dict[str, Any]:
	queue_doc = frappe.get_doc("Attachment Queue", attachment_queue)
	queue_doc.check_permission("read")

	# Taking the caller's doctype here would re-target the row without going through set_document_type,
	# which is where the upload-first check lives.
	if document_type != queue_doc.document_type:
		frappe.throw(
			_("Attachment Queue {0} is for {1}, not {2}.").format(
				frappe.bold(queue_doc.name),
				frappe.bold(_(queue_doc.document_type)),
				frappe.bold(_(document_type)),
			)
		)

	# Linking twice would strand the first document's attachment: the source file has
	# already moved off the queue row by then, so the second link silently loses it.
	if queue_doc.status not in REVIEWABLE_STATUSES:
		frappe.throw(
			_("Attachment Queue {0} is {1} and cannot be linked again.").format(
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
	target_doc.check_permission("write")
	queue_doc.mark_review_completed(target_doc.doctype, target_doc.name)
	attach_source_file_to_document(queue_doc, target_doc)

	return {
		"ok": True,
		"status": queue_doc.status,
		"document_type": queue_doc.document_type,
		"created_document": queue_doc.created_document,
	}


def attach_source_file_to_document(queue_doc: AttachmentQueue, target_doc: Document):
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
		return

	file_doc = frappe.get_doc("File", file_doc_name)
	file_doc.db_set(
		{
			"attached_to_doctype": target_doc.doctype,
			"attached_to_name": target_doc.name,
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
	return bool(values and cint(values.enable_upload_first_workflow) and not cint(values.istable))


def extract_file(file_path: str) -> dict[str, Any]:
	if _is_image(file_path):
		return extract_image(file_path)

	if _is_pdf(file_path):
		return extract_pdf(file_path)

	raise UnsupportedExtractionFile(_("Only PDF and image extraction is supported for Attachment Queue"))


def extract_image(file_path: str) -> dict[str, Any]:
	"""Accept an image without extracting text from it.

	The framework ships no image text extraction: an image is a valid queue input that
	the reviewer reads off the preview pane and keys in by hand. This is the seam an app
	that brings its own extraction backend replaces — the queue lifecycle around it, and
	the shape of the result below, stay the same.
	"""
	return {
		"extraction_method": EXTRACTION_METHOD_PREVIEW_ONLY,
		"extracted_text": "",
		"raw_extraction_json": {
			"file": Path(file_path).name,
			"extraction_method": EXTRACTION_METHOD_PREVIEW_ONLY,
			"pages": [],
		},
		"debug_output": ["No text extraction is performed for images; preview only."],
	}


def extract_pdf(file_path: str) -> dict[str, Any]:
	pdfplumber = _get_pdfplumber()
	pages = []
	text_parts = []
	layout_text_parts = []

	with pdfplumber.open(file_path) as pdf:
		for page_number, page in enumerate(pdf.pages, start=1):
			text = page.extract_text() or ""
			layout_text = page.extract_text(layout=True) or ""
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

	return {
		"extraction_method": EXTRACTION_METHOD_PDFPLUMBER,
		"extracted_text": extracted_layout_text or extracted_text,
		"raw_extraction_json": {
			"file": Path(file_path).name,
			"extraction_method": EXTRACTION_METHOD_PDFPLUMBER,
			"pages": pages,
		},
		"debug_output": [],
	}


def _get_pdfplumber():
	try:
		return importlib.import_module("pdfplumber")
	except ImportError:
		frappe.throw(
			_("pdfplumber is required to extract PDF text. Please install project dependencies."),
			frappe.ValidationError,
		)


def _is_pdf(path_or_url: str) -> bool:
	return path_or_url.lower().split("?", 1)[0].endswith(".pdf")


# An image reaches review to be read off the preview pane, so the set is bounded by
# what a browser will actually render in an <img>; TIFF is deliberately absent for that
# reason. Keep this in step with image_extensions in attachment_queue_review.js.
def _is_image(path_or_url: str) -> bool:
	return Path(path_or_url.lower().split("?", 1)[0]).suffix in {
		".bmp",
		".gif",
		".jpeg",
		".jpg",
		".png",
		".webp",
	}


def _parse_json(value: str | dict | list | None):
	if not value:
		return {}
	if isinstance(value, (dict, list)):
		return value
	try:
		return json.loads(value)
	except Exception:
		return {}


def _get_source_file_preview_url(queue_doc: AttachmentQueue) -> str:
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

	file_doc = frappe.get_doc("File", file_doc_name)
	return file_doc.unique_url


def _json_safe(value):
	return json.loads(json.dumps(value, default=str))


def has_permission(doc, ptype="read", user=None):
	"""Mirror the target DocType's permissions onto the queue row.

	Controller hooks can only deny, never grant (see `has_controller_permissions`), so this
	narrows Attachment Queue's own DocPerms rather than widening them: a queue row is only as
	reachable as the DocType it feeds.
	"""
	if not doc or not getattr(doc, "document_type", None):
		# `document_type` is mandatory, so this is the pre-target case only. Such a row stays
		# governed by Attachment Queue's own owner-scoped DocPerms.
		return True

	return frappe.has_permission(doc.document_type, ptype=ptype, user=user)


def get_permission_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user

	if user == "Administrator":
		return ""

	from frappe.permissions import get_doctypes_with_read

	readable_doctypes = ", ".join(frappe.db.escape(dt) for dt in get_doctypes_with_read(user))

	if not readable_doctypes:
		return "1=0"

	return f"`tabAttachment Queue`.`document_type` IN ({readable_doctypes})"
