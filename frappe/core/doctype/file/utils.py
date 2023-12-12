import hashlib
import imghdr
import mimetypes
import os
import re
from io import BytesIO
from typing import TYPE_CHECKING, Optional
from urllib.parse import unquote

import requests
import requests.exceptions
from PIL import Image

import frappe
from frappe import _, safe_decode
from frappe.utils import cint, cstr, encode, get_files_path, random_string, strip
from frappe.utils.file_manager import safe_b64decode
from frappe.utils.image import optimize_image

if TYPE_CHECKING:
	from PIL.ImageFile import ImageFile
	from requests.models import Response

	from frappe.model.document import Document

	from .file import File


def make_home_folder() -> None:
	home = frappe.get_doc(
		{"doctype": "File", "is_folder": 1, "is_home_folder": 1, "file_name": _("Home")}
	).insert(ignore_if_duplicate=True)

	frappe.get_doc(
		{
			"doctype": "File",
			"folder": home.name,
			"is_folder": 1,
			"is_attachments_folder": 1,
			"file_name": _("Attachments"),
		}
	).insert(ignore_if_duplicate=True)


def setup_folder_path(filename: str, new_parent: str) -> None:
	file: "File" = frappe.get_doc("File", filename)
	file.folder = new_parent
	file.save()

	if file.is_folder:
		from frappe.model.rename_doc import rename_doc

		rename_doc("File", file.name, file.get_name_based_on_parent_folder(), ignore_permissions=True)


def get_extension(
	filename,
	extn: str | None = None,
	content: bytes | None = None,
	response: Optional["Response"] = None,
) -> str:
	mimetype = None

	if response:
		content_type = response.headers.get("Content-Type")

		if content_type:
			_extn = mimetypes.guess_extension(content_type)
			if _extn:
				return _extn[1:]

	if extn:
		# remove '?' char and parameters from extn if present
		if "?" in extn:
			extn = extn.split("?", 1)[0]

		mimetype = mimetypes.guess_type(filename + "." + extn)[0]

	if mimetype is None or not mimetype.startswith("image/") and content:
		# detect file extension by reading image header properties
		extn = imghdr.what(filename + "." + (extn or ""), h=content)

	return extn


def get_local_image(file_url: str) -> tuple["ImageFile", str, str]:
	if file_url.startswith("/private"):
		file_url_path = (file_url.lstrip("/"),)
	else:
		file_url_path = ("public", file_url.lstrip("/"))

	file_path = frappe.get_site_path(*file_url_path)

	try:
		image = Image.open(file_path)
	except OSError:
		frappe.throw(_("Unable to read file format for {0}").format(file_url))

	content = None

	try:
		filename, extn = file_url.rsplit(".", 1)
	except ValueError:
		# no extn
		with open(file_path) as f:
			content = f.read()

		filename = file_url
		extn = None

	extn = get_extension(filename, extn, content)

	return image, filename, extn


def get_web_image(file_url: str) -> tuple["ImageFile", str, str]:
	# download
	file_url = frappe.utils.get_url(file_url)
	r = requests.get(file_url, stream=True)
	try:
		r.raise_for_status()
	except requests.exceptions.HTTPError as e:
		if "404" in e.args[0]:
			frappe.msgprint(_("File '{0}' not found").format(file_url))
		else:
			frappe.msgprint(_("Unable to read file format for {0}").format(file_url))
		raise

	try:
		image = Image.open(BytesIO(r.content))
	except Exception as e:
		frappe.msgprint(_("Image link '{0}' is not valid").format(file_url), raise_exception=e)

	try:
		filename, extn = file_url.rsplit("/", 1)[1].rsplit(".", 1)
	except ValueError:
		# the case when the file url doesn't have filename or extension
		# but is fetched due to a query string. example: https://encrypted-tbn3.gstatic.com/images?q=something
		filename = get_random_filename()
		extn = None

	extn = get_extension(filename, extn, r.content)
	filename = "/files/" + strip(unquote(filename))

	return image, filename, extn


def delete_file(path: str) -> None:
	"""Delete file from `public folder`"""
	if path:
		if ".." in path.split("/"):
			frappe.throw(
				_("It is risky to delete this file: {0}. Please contact your System Manager.").format(path)
			)

		parts = os.path.split(path.strip("/"))
		if parts[0] == "files":
			path = frappe.utils.get_site_path("public", "files", parts[-1])

		else:
			path = frappe.utils.get_site_path("private", "files", parts[-1])

		path = encode(path)
		if os.path.exists(path):
			os.remove(path)


def remove_file_by_url(file_url: str, doctype: str = None, name: str = None) -> "Document":
	if doctype and name:
		fid = frappe.db.get_value(
			"File", {"file_url": file_url, "attached_to_doctype": doctype, "attached_to_name": name}
		)
	else:
		fid = frappe.db.get_value("File", {"file_url": file_url})

	if fid:
		from frappe.utils.file_manager import remove_file

		return remove_file(fid=fid)


def get_content_hash(content: bytes | str) -> str:
	if isinstance(content, str):
		content = content.encode()
	return hashlib.md5(content).hexdigest()  # nosec


def generate_file_name(name: str, suffix: str | None = None, is_private: bool = False) -> str:
	"""Generate conflict-free file name. Suffix will be ignored if name available. If the
	provided suffix doesn't result in an available path, a random suffix will be picked.
	"""

	def path_exists(name, is_private):
		return os.path.exists(encode(get_files_path(name, is_private=is_private)))

	if not path_exists(name, is_private):
		return name

	candidate_path = get_file_name(name, suffix)

	if path_exists(candidate_path, is_private):
		return generate_file_name(name, is_private=is_private)
	return candidate_path


def get_file_name(fname: str, optional_suffix: str | None = None) -> str:
	# convert to unicode
	fname = cstr(fname)
	partial, extn = os.path.splitext(fname)
	suffix = optional_suffix or frappe.generate_hash(length=6)

	return f"{partial}{suffix}{extn}"


def extract_images_from_doc(doc: "Document", fieldname: str):
	content = doc.get(fieldname)
	content = extract_images_from_html(doc, content)
	if frappe.flags.has_dataurl:
		doc.set(fieldname, content)


def extract_images_from_html(doc: "Document", content: str, is_private: bool = False):
	frappe.flags.has_dataurl = False

	def _save_file(match):
		data = match.group(1).split("data:")[1]
		headers, content = data.split(",")
		mtype = headers.split(";", 1)[0]

		if isinstance(content, str):
			content = content.encode("utf-8")
		if b"," in content:
			content = content.split(b",")[1]
		content = safe_b64decode(content)

		content = optimize_image(content, mtype)

		if "filename=" in headers:
			filename = headers.split("filename=")[-1]
			filename = safe_decode(filename).split(";", 1)[0]

		else:
			filename = get_random_filename(content_type=mtype)

		if doc.meta.istable:
			doctype = doc.parenttype
			name = doc.parent
		else:
			doctype = doc.doctype
			name = doc.name

		_file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": filename,
				"attached_to_doctype": doctype,
				"attached_to_name": name,
				"content": content,
				"decode": False,
				"is_private": is_private,
			}
		)
		_file.save(ignore_permissions=True)
		file_url = _file.file_url
		frappe.flags.has_dataurl = True

		return f'<img src="{file_url}"'

	if content and isinstance(content, str):
		content = re.sub(r'<img[^>]*src\s*=\s*["\'](?=data:)(.*?)["\']', _save_file, content)

	return content


def get_random_filename(content_type: str = None) -> str:
	extn = None
	if content_type:
		extn = mimetypes.guess_extension(content_type)

	return random_string(7) + (extn or "")


def update_existing_file_docs(doc: "File") -> None:
	# Update is private and file url of all file docs that point to the same file
	file_doctype = frappe.qb.DocType("File")
	(
		frappe.qb.update(file_doctype)
		.set(file_doctype.file_url, doc.file_url)
		.set(file_doctype.is_private, doc.is_private)
		.where(file_doctype.content_hash == doc.content_hash)
		.where(file_doctype.name != doc.name)
	).run()


def attach_files_to_document(doc: "Document", event) -> None:
	"""Runs on on_update hook of all documents.
	Goes through every file linked with the Attach and Attach Image field and attaches
	the file to the document if not already attached. If no file is found, a new file
	is created.
	"""

	attach_fields = doc.meta.get("fields", {"fieldtype": ["in", ["Attach", "Attach Image"]]})

	for df in attach_fields:
		# this method runs in on_update hook of all documents
		# we dont want the update to fail if file cannot be attached for some reason
		value = doc.get(df.fieldname)
		if not (value or "").startswith(("/files", "/private/files")):
			continue

		if frappe.db.exists(
			"File",
			{
				"file_url": value,
				"attached_to_name": doc.name,
				"attached_to_doctype": doc.doctype,
				"attached_to_field": df.fieldname,
			},
		):
			continue

		unattached_file = frappe.db.exists(
			"File",
			{
				"file_url": value,
				"attached_to_name": None,
				"attached_to_doctype": None,
				"attached_to_field": None,
			},
		)

		if unattached_file:
			frappe.db.set_value(
				"File",
				unattached_file,
				field={
					"attached_to_name": doc.name,
					"attached_to_doctype": doc.doctype,
					"attached_to_field": df.fieldname,
					"is_private": cint(value.startswith("/private")),
				},
			)
			continue

		file: "File" = frappe.get_doc(
			doctype="File",
			file_url=value,
			attached_to_name=doc.name,
			attached_to_doctype=doc.doctype,
			attached_to_field=df.fieldname,
			folder="Home/Attachments",
		)
		try:
			file.insert(ignore_permissions=True)
		except Exception:
			doc.log_error("Error Attaching File")


def relink_files(doc, fieldname, temp_doc_name):
	if not temp_doc_name:
		return
	from frappe.utils.data import add_to_date, now_datetime

	"""
	Relink files attached to incorrect document name to the new document name
	by check if file with temp name exists that was created in last 60 minutes
	"""
	mislinked_file = frappe.db.exists(
		"File",
		{
			"file_url": doc.get(fieldname),
			"attached_to_name": temp_doc_name,
			"attached_to_doctype": doc.doctype,
			"attached_to_field": fieldname,
			"creation": (
				"between",
				[add_to_date(date=now_datetime(), minutes=-60), now_datetime()],
			),
		},
	)
	"""If file exists, attach it to the new docname"""
	if mislinked_file:
		frappe.db.set_value(
			"File",
			mislinked_file,
			field={
				"attached_to_name": doc.name,
			},
		)
		return


def relink_mismatched_files(doc: "Document") -> None:
	if not doc.get("__temporary_name", None):
		return
	attach_fields = doc.meta.get("fields", {"fieldtype": ["in", ["Attach", "Attach Image"]]})
	for df in attach_fields:
		if doc.get(df.fieldname):
			relink_files(doc, df.fieldname, doc.__temporary_name)
	# delete temporary name after relinking is done
	doc.delete_key("__temporary_name")


def decode_file_content(content: bytes) -> bytes:
	if isinstance(content, str):
		content = content.encode("utf-8")
	if b"," in content:
		content = content.split(b",")[1]
	return safe_b64decode(content)
