import mimetypes

import frappe


def execute():
	"""Set 'File Type' for all files based on file extension."""
	files = frappe.db.get_all(
		"File",
		fields=["name", "file_name", "file_url"],
		filters={"is_folder": 0, "file_type": ("is", "not set")},
	)

	frappe.db.auto_commit_on_many_writes = 1

	for file in files:
		file_extension = get_file_extension(file.file_name or file.file_url)
		if file_extension:
			frappe.db.set_value("File", file.name, "file_type", file_extension, update_modified=False)

	frappe.db.auto_commit_on_many_writes = 0


def get_file_extension(file_name):
	if not file_name:
		return None
	file_type = mimetypes.guess_type(file_name)[0]
	if not file_type:
		return None

	file_extension = mimetypes.guess_extension(file_type)
	return file_extension.lstrip(".").upper() if file_extension else None
