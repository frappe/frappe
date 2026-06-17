import json

import frappe
from frappe.core.doctype.file.file import File
from frappe.core.doctype.file.utils import setup_folder_path
from frappe.utils import cint, cstr


@frappe.whitelist()
def unzip_file(name: str):
	"""Unzip the given file and make file records for each of the extracted files"""
	file: File = frappe.get_doc("File", name)
	return file.unzip()


@frappe.whitelist()
def get_attached_images(doctype: str, names: list[str] | str) -> frappe._dict:
	"""Return list of image urls attached in form `{name: ['image.jpg', 'image.png']}`."""

	if isinstance(names, str):
		names = json.loads(names)

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


@frappe.whitelist()
def get_files_in_folder(folder: str, start: int = 0, page_length: int = 20) -> dict:
	fields = ["name", "file_name", "file_url", "is_folder", "modified"]

	attachment_folder = frappe.db.get_value("File", "Home/Attachments", fields, as_dict=1)
	is_first_page = cint(start)
	folders = []
	if is_first_page == 0:
		folders = frappe.get_list("File", {"folder": folder, "is_folder": 1}, fields)

	files = frappe.get_list(
		"File",
		{"folder": folder, "is_folder": 0},
		fields,
		start=start,
		page_length=page_length + 1,
		group_by="file_url",
	)
	result = folders + files[:page_length]

	if folder == "Home" and is_first_page == 0 and attachment_folder and attachment_folder not in result:
		result.insert(0, attachment_folder)

	return {"files": result, "has_more": len(files) > page_length}


@frappe.whitelist()
def get_files_by_search_text(text: str) -> list[dict]:
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
		# Results are all files (is_folder=False), so collapse duplicates that
		# point to the same blob (same file_url) to one entry.
		group_by="file_url",
		limit=20,
	)


@frappe.whitelist(allow_guest=True)
def get_max_file_size() -> int:
	return (
		cint(frappe.get_system_settings("max_file_size")) * 1024 * 1024
		or cint(frappe.conf.get("max_file_size"))
		or 25 * 1024 * 1024
	)


def get_file_chunk_size() -> int:
	return cint(frappe.conf.get("file_chunk_size")) or 25 * 1024 * 1024


@frappe.whitelist()
def create_new_folder(file_name: str, folder: str) -> File:
	"""create new folder under current parent folder"""
	file = frappe.new_doc("File")
	file.file_name = file_name
	file.is_folder = 1
	file.folder = folder
	file.insert(ignore_if_duplicate=True)
	return file


@frappe.whitelist()
def move_file(file_list: list[File | dict] | str, new_parent: str, old_parent: str) -> None:
	if isinstance(file_list, str):
		file_list = json.loads(file_list)

	# will check for permission on each file & update parent
	for file_obj in file_list:
		setup_folder_path(file_obj.get("name"), new_parent)

	# recalculate sizes
	frappe.get_doc("File", old_parent).save()
	frappe.get_doc("File", new_parent).save()


@frappe.whitelist()
def zip_files(files: str):
	files = frappe.parse_json(files)
	frappe.response["filename"] = "files.zip"
	frappe.response["filecontent"] = File.zip_files(files)
	frappe.response["type"] = "download"
