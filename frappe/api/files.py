"""File handlers for the v2 document routes.

`POST /document/File` uploads a detached file and `POST /document/<dt>/<name>/attachments`
one that hangs on a record; `DELETE .../attachments/<file>` removes it.
"""

import frappe
from frappe import _
from frappe.api.include import DOCUMENT_PARTS, USERS_PART, users_named_by
from frappe.handler import upload_file
from frappe.model.document import Document

ATTACHMENTS = "attachments"

# the fields that name a record; on this route they would make a second way to attach
ATTACH_FIELDS = ("doctype", "docname")


def create_file():
	"""Multipart is an upload; JSON stays the plain insert, so base64 `content` still works."""
	if not has_upload_part():
		from frappe.api.v2 import create_doc

		return create_doc("File")

	for field in ATTACH_FIELDS:
		if frappe.form_dict.get(field):
			raise NotAnUploadError(
				_("'{0}' belongs to the attachments route, not the File route").format(field)
			)
	doc = upload()
	return doc.as_dict() if doc else None


def attach(doctype: str, name: str):
	"""Upload a file and hang it on the document; answers with the refreshed part and the new File."""
	if not has_upload_part():
		raise NotAnUploadError(_("Attaching a file needs a multipart request with a 'file' part"))

	# `upload_file` reads the document it attaches to from the form, and checks `write` on it
	frappe.form_dict["doctype"] = doctype
	frappe.form_dict["docname"] = name

	created = upload()
	if not created:
		return None
	# two files can share a name, so the part alone does not say which row this request made
	return {"file": created.name, **refreshed(frappe.get_doc(doctype, name))}


def detach(doctype: str, name: str, file_name: str):
	"""Delete a file attached to the document; answers with the refreshed part."""
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("write")
	frappe.delete_doc("File", attachment_of(doc, file_name).name)
	return refreshed(doc)


class NotAnUploadError(frappe.ValidationError):
	http_status_code = 417


def has_upload_part() -> bool:
	"""Whether the request carries file bytes, rather than a JSON body."""
	return bool(frappe.request and frappe.request.files and "file" in frappe.request.files)


def upload() -> Document | None:
	"""The shared upload: permissions, chunks, image optimize and the `after_file_upload` hooks."""
	if frappe.form_dict.get("method"):
		raise NotAnUploadError(_("'method' belongs to the upload_file method route, not a document route"))

	doc = upload_file()
	if doc:
		return doc

	# Every chunk goes to the same route and only the last one answers with the File, so the
	# envelope must still carry the key the caller reads.
	frappe.response["data"] = None
	return None


def refreshed(doc: Document) -> dict:
	rows = DOCUMENT_PARTS[ATTACHMENTS](doc)
	return {ATTACHMENTS: rows, USERS_PART: users_named_by(doc, {ATTACHMENTS: rows})}


def attachment_of(doc: Document, file_name: str) -> Document:
	"""The File `file_name`, which must be attached to `doc`."""
	file = frappe.get_doc("File", file_name)
	on_doc = file.attached_to_doctype == doc.doctype and file.attached_to_name == str(doc.name)
	if not on_doc:
		raise frappe.DoesNotExistError(
			_("File {0} is not attached to {1} {2}").format(file_name, doc.doctype, doc.name)
		)
	return file
