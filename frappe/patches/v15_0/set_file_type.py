import frappe


def execute():
	"""Set 'File Type' for all files based on file extension."""
	files = frappe.db.get_all(
		"File",
		fields=["name", "file_name", "is_folder"],
	)

	for file in files:
		if file.get("is_folder"):
			continue

		file_name = file.get("file_name").split("?")[0]
		file_extension = file_name.split(".")[-1].upper() if file_name.split(".")[-1] else None
		if file_extension:
			frappe.db.set_value("File", file.get("name"), "file_type", file_extension)
