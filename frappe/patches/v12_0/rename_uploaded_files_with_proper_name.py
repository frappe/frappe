import frappe
import os

def execute():
	file_names_with_url = frappe.get_all("File", filters={
		"is_folder": 0,
		"file_name": ["like", "%/%"]
	}, fields=['name', 'file_name', 'file_url'])

	for f in file_names_with_url:
		filename = f.file_name.rsplit('/', 1)[-1]

		if not f.file_url:
			f.file_url = f.file_name

		if not file_exists(f.file_url):
			continue

		frappe.db.set_values('File', f.name, {
			"file_name": filename,
			"file_url": f.file_url
		})

	files_without_filename = frappe.get_all("File", filters={
		"is_folder": 0,
		"file_name": ["is", "not set"],
		"file_url": ["is", "set"]
	}, fields=['file_url', 'name'])

	for f in files_without_filename:
		filename = f.file_url.rsplit('/', 1)[-1]
		frappe.db.set_value("File", f.name, "file_name", filename)

def file_exists(file_path):
	file_path = frappe.utils.get_site_path(file_path.lstrip('/'))
	return os.path.exists(file_path)
