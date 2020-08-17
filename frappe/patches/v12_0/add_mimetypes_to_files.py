import frappe
import os
from frappe.utils.file_manager import guess_mimetype

def execute():
	# Reload doctype changes
	frappe.reload_doc('core', 'doctype', 'file', force=True)

	files = frappe.get_all('File',
		fields = ['name', 'file_url'],
		filters = {
			'is_folder': 0,
			'file_url': ['!=', ''],
		})

	for file in files:
		guessed_type = guess_mimetype(file.file_url)[0]
		if guessed_type:
			frappe.db.set_value("File", file.name, "mimetype", guessed_type)

