# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Public file API — upload, download and manage File documents.

`upload_file` and `download_file` were consolidated here from
`frappe.handler`; their old dotted paths (and the bare `upload_file` cmd
shorthand) keep working via aliases there.
"""

import os
from mimetypes import guess_type
from pathlib import Path
from typing import TYPE_CHECKING

import frappe
from frappe import _, is_whitelisted
from frappe.core.doctype.file.file import File
from frappe.core.doctype.file.utils import find_file_by_url, get_safe_file_name, setup_folder_path
from frappe.public_api import public
from frappe.utils import cint, cstr, get_files_path
from frappe.utils.image import optimize_image

if TYPE_CHECKING:
	from frappe.core.doctype.user.user import User

ALLOWED_MIMETYPES = (
	"image/png",
	"image/jpeg",
	"image/gif",
	"application/pdf",
	"application/msword",
	"application/vnd.openxmlformats-officedocument.wordprocessingml.document",
	"application/vnd.ms-excel",
	"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
	"application/vnd.oasis.opendocument.text",
	"application/vnd.oasis.opendocument.spreadsheet",
	"text/plain",
	"video/quicktime",
	"video/mp4",
	"text/csv",
)


@public(group="Files")
@frappe.whitelist(allow_guest=True, methods=["POST"])
def upload_file() -> "File | None":
	"""Upload a file (multipart or chunked) and create a File document.

	Reads the file and its options (doctype, docname, fieldname, folder,
	is_private, optimize, chunking parameters) from the request form data.
	Guest uploads require the "allow guests to upload files" system setting.

	:return: The created File document, or None while a chunked upload is incomplete.
	"""
	user = None
	if frappe.session.user == "Guest":
		if frappe.get_system_settings("allow_guests_to_upload_files"):
			ignore_permissions = True
			guest_allowed_docs = frappe.get_system_settings("allowed_doctypes_for_guest_uploads")
			if guest_allowed_docs:
				target_doctype = frappe.form_dict.doctype
				allowed_docs = guest_allowed_docs.splitlines()
				allowed_docs = [doc.strip() for doc in allowed_docs if doc.strip()]
				if allowed_docs and target_doctype not in allowed_docs:
					frappe.throw(
						_("Guests are not allowed to upload files for {0} Doctype").format(target_doctype),
						frappe.PermissionError,
					)
		else:
			raise frappe.PermissionError
	else:
		user: User = frappe.get_lazy_doc("User", frappe.session.user)
		ignore_permissions = False

	files = frappe.request.files
	is_private = frappe.form_dict.get("is_private", 1)
	doctype = frappe.form_dict.doctype
	docname = frappe.form_dict.docname
	fieldname = frappe.form_dict.fieldname
	file_url = frappe.form_dict.file_url
	folder = frappe.form_dict.folder or "Home"
	method = frappe.form_dict.method
	filename = frappe.form_dict.file_name
	optimize = frappe.form_dict.optimize
	content = None

	if library_file := frappe.form_dict.get("library_file_name"):
		frappe.has_permission("File", doc=library_file, throw=True)
		doc = frappe.get_value(
			"File",
			frappe.form_dict.library_file_name,
			["is_private", "file_url", "file_name"],
			as_dict=True,
		)
		is_private = doc.is_private
		file_url = doc.file_url
		filename = doc.file_name

	if not ignore_permissions:
		check_write_permission(doctype, docname)

	if "file" in files:
		file = files["file"]
		filename = file.filename

		if frappe.form_dict.get("chunk_index") is not None:
			current_chunk = int(frappe.form_dict.chunk_index)
			total_chunks = int(frappe.form_dict.total_chunk_count)
			offset = int(frappe.form_dict.chunk_byte_offset)
		else:
			offset = 0
			current_chunk = 0
			total_chunks = 1

		temp_path = Path(get_files_path(".temp-" + get_safe_file_name(filename), is_private=is_private))
		with temp_path.open("ab" if current_chunk > 0 else "wb") as f:
			total_file_size = frappe.form_dict.total_file_size or 0
			f.seek(offset)
			f.write(file.stream.read())
			if not f.tell() >= int(total_file_size) or current_chunk != total_chunks - 1:
				return

		content = temp_path.read_bytes()
		temp_path.unlink()
		content_type = guess_type(filename)[0]
		if optimize and content_type and content_type.startswith("image/"):
			args = {"content": content, "content_type": content_type}
			if frappe.form_dict.max_width:
				args["max_width"] = int(frappe.form_dict.max_width)
			if frappe.form_dict.max_height:
				args["max_height"] = int(frappe.form_dict.max_height)
			content = optimize_image(**args)

	frappe.local.uploaded_file_url = file_url
	frappe.local.uploaded_file = content
	frappe.local.uploaded_filename = filename

	if content is not None and (frappe.session.user == "Guest" or (user and not user.has_desk_access())):
		filetype = guess_type(filename)[0]
		if filetype not in ALLOWED_MIMETYPES:
			frappe.throw(_("You can only upload JPG, PNG, GIF, PDF, TXT, CSV or Microsoft documents."))

	if method:
		method = frappe.get_attr(method)
		is_whitelisted(method)
		return method()
	else:
		doc = frappe.get_doc(
			{
				"doctype": "File",
				"attached_to_doctype": doctype,
				"attached_to_name": docname,
				"attached_to_field": fieldname,
				"folder": folder,
				"file_name": filename,
				"file_url": file_url,
				"is_private": cint(is_private),
				"content": content,
			}
		)
		funcs = frappe.get_hooks("after_file_upload")
		for func in funcs:
			doc = frappe.call(func, doc=doc)
		return doc.save(ignore_permissions=ignore_permissions)


def check_write_permission(doctype: str | None = None, name: str | None = None):
	if not doctype:
		return

	if not name:
		frappe.has_permission(doctype, "write", throw=True)
		return

	try:
		frappe.get_lazy_doc(doctype, name, check_permission="write")
	except frappe.DoesNotExistError:
		# doc has not been inserted yet, name is set to "new-some-doctype"
		# If doc inserts fine then only this attachment will be linked see file/utils.py:relink_mismatched_files
		frappe.new_doc(doctype).check_permission("write")
		return


@public(group="Files")
@frappe.whitelist(allow_guest=True)
def download_file(file_url: str) -> None:
	"""Download a file; a valid session or token is required for private files.

	:param file_url: path of the file relative to the site path
	:raises frappe.PermissionError: If the file does not exist or is not accessible.
	"""
	file = find_file_by_url(file_url)
	if not file:
		raise frappe.PermissionError

	frappe.local.response.filename = os.path.basename(file_url)
	frappe.local.response.filecontent = file.get_content()
	frappe.local.response.type = "download"


@public(group="Files")
@frappe.whitelist()
def add_attachments(doctype: str, name: str | int, attachments: str | list[str]) -> list:
	"""Attach existing File documents to a document.

	:param doctype: DocType of the document to attach files to
	:param name: name of the document to attach files to
	:param attachments: names of File documents to be attached
	:return: The newly created File documents.
	"""
	from frappe.utils.file_manager import save_url

	if not frappe.has_permission(doctype, "write", doc=name):
		frappe.throw(_("You need write permissions to add attachments to this record."))

	attachments = frappe.parse_json(attachments)
	# loop through attachments
	files = []
	for a in attachments:
		if isinstance(a, str):
			if not frappe.has_permission("File", ptype="read", doc=a):
				frappe.throw(_("You don't have permission to read/attach the file {0}.").format(a))

			attach = frappe.db.get_value(
				"File", {"name": a}, ["file_name", "file_url", "is_private"], as_dict=1
			)
			# save attachments to new doc
			f = save_url(
				attach.file_url, attach.file_name, doctype, name, "Home/Attachments", attach.is_private
			)
			files.append(f)

	return files


@public(group="Files")
@frappe.whitelist()
def unzip_file(name: str) -> list:
	"""Unzip the given file and make file records for each of the extracted files.

	:param name: name of the zip File document
	:return: The extracted File documents.
	"""
	file: File = frappe.get_doc("File", name)
	return file.unzip()


@public(group="Files")
@frappe.whitelist()
def get_attached_images(doctype: str, names: list[str] | str) -> frappe._dict:
	"""Return list of image urls attached in form `{name: ['image.jpg', 'image.png']}`.

	:param doctype: DocType of the documents
	:param names: names of the documents
	:return: Dict mapping each document name to its attached image urls.
	"""

	names = frappe.parse_json(names)

	img_urls = frappe.db.get_list(
		"File",
		filters={
			"attached_to_doctype": doctype,
			"attached_to_name": ("in", names),
			"is_folder": 0,
		},
		fields=["file_url", "attached_to_name as docname"],
	)

	out = frappe._dict()
	for i in img_urls:
		out[i.docname] = out.get(i.docname, [])
		out[i.docname].append(i.file_url)

	return out


@public(group="Files")
@frappe.whitelist()
def get_files_in_folder(folder: str, start: int = 0, page_length: int = 20) -> dict:
	"""Return the files in the given folder, for the file browser.

	:param folder: name of the folder File document
	:param start: start at this index
	:param page_length: number of files to return
	:return: Dict with `files` and a `has_more` flag.
	"""
	attachment_folder = frappe.db.get_value(
		"File",
		"Home/Attachments",
		["name", "file_name", "file_url", "is_folder", "modified"],
		as_dict=1,
	)

	files = frappe.get_list(
		"File",
		{"folder": folder},
		["name", "file_name", "file_url", "is_folder", "modified"],
		start=start,
		page_length=page_length + 1,
	)

	if folder == "Home" and attachment_folder not in files:
		files.insert(0, attachment_folder)

	return {"files": files[:page_length], "has_more": len(files) > page_length}


@public(group="Files")
@frappe.whitelist()
def get_files_by_search_text(text: str) -> list[dict]:
	"""Search files by name or url.

	:param text: text to search for
	:return: The matching File documents, newest first.
	"""
	if not text:
		return []

	text = "%" + cstr(text).lower() + "%"
	return frappe.get_list(
		"File",
		fields=["name", "file_name", "file_url", "is_folder", "modified"],
		filters={"is_folder": False},
		or_filters={
			"file_name": ("like", text),
			"file_url": text,
			"name": ("like", text),
		},
		order_by="creation desc",
		limit=20,
	)


@public(group="Files")
@frappe.whitelist(allow_guest=True)
def get_max_file_size() -> int:
	"""Return the maximum upload size configured for the site, in bytes.

	:return: Maximum file size in bytes.
	"""
	return (
		cint(frappe.get_system_settings("max_file_size")) * 1024 * 1024
		or cint(frappe.conf.get("max_file_size"))
		or 25 * 1024 * 1024
	)


def get_file_chunk_size() -> int:
	return cint(frappe.conf.get("file_chunk_size")) or 25 * 1024 * 1024


@public(group="Files")
@frappe.whitelist()
def create_new_folder(file_name: str, folder: str) -> File:
	"""Create a new folder under the given parent folder.

	:param file_name: name of the new folder
	:param folder: name of the parent folder File document
	:return: The created folder's File document.
	"""
	file = frappe.new_doc("File")
	file.file_name = file_name
	file.is_folder = 1
	file.folder = folder
	file.insert(ignore_if_duplicate=True)
	return file


@public(group="Files")
@frappe.whitelist()
def move_file(file_list: list[File | dict] | str, new_parent: str, old_parent: str) -> None:
	"""Move files to another folder.

	:param file_list: the File documents (or their dicts/JSON) to be moved
	:param new_parent: name of the destination folder
	:param old_parent: name of the current folder
	"""
	file_list = frappe.parse_json(file_list)

	# will check for permission on each file & update parent
	for file_obj in file_list:
		setup_folder_path(file_obj.get("name"), new_parent)

	# recalculate sizes
	frappe.get_doc("File", old_parent).save()
	frappe.get_doc("File", new_parent).save()


@public(group="Files")
@frappe.whitelist()
def zip_files(files: str) -> None:
	"""Download the given files bundled into a zip archive.

	:param files: names of the File documents to be zipped
	"""
	files = frappe.parse_json(files)
	frappe.response["filename"] = "files.zip"
	frappe.response["filecontent"] = File.zip_files(files)
	frappe.response["type"] = "download"
