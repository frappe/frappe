import frappe


def execute():
	"""Delete the screenshots print formats used to keep as their thumbnail.

	The settings grid renders each format live now, so these files have no reader —
	and since they were attached to the format, every regeneration left another one
	in its Attachments. The column is cleared first: a File still named by it can't
	be deleted, and the field itself is gone from the DocType.
	"""
	if frappe.db.has_column("Print Format", "preview_image"):
		frappe.db.sql("update `tabPrint Format` set preview_image = null where preview_image is not null")

	files = frappe.get_all(
		"File",
		filters={
			"attached_to_doctype": "Print Format",
			"file_name": ("like", "pf-preview-%"),
		},
		pluck="name",
	)
	for name in files:
		try:
			frappe.delete_doc("File", name, ignore_permissions=True, delete_permanently=True)
		except Exception:
			frappe.clear_last_message()
