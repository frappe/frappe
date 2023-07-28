import mimetypes

import frappe


def execute():
	"""Set 'File Type' for all files based on file extension."""
	files = frappe.db.get_all(
		"File",
		fields=["name", "file_name", "is_folder"],
	)

	frappe.db.auto_commit_on_many_writes = 1

	for file in files:
		if file.get("is_folder"):
			continue

		file_extension = get_file_extension(file.get("file_name"))
		if file_extension:
			frappe.db.set_value(
				"File", file.get("name"), "file_type", file_extension, update_modified=False
			)

	frappe.db.auto_commit_on_many_writes = 0


def get_file_extension(file_name):
	file_type = mimetypes.guess_type(file_name)[0]
	if not file_type:
		return None

	file_extension = mimetypes.guess_extension(file_type)
	return file_extension.lstrip(".").upper() if file_extension else None
