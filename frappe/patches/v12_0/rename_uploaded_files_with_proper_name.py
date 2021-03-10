import frappe
import os


def execute():

	public_path = frappe.utils.get_files_path()
	private_path = frappe.utils.get_files_path(is_private=1)

	file_names_with_url_and_file_url_not_set = frappe.get_all("File", filters={
		"is_folder": 0,
		"file_url": ["is", "not set"],
		"file_name": ["like", "%/%"]
	}, fields=['name', 'file_name'])

	for f in file_names_with_url_and_file_url_not_set:
		fileurl = f.file_name
		filename = f.file_name.rsplit('/', 1)[-1]

		# Check if file exists
		path = os.path.join(public_path, filename)
		if '/private/' in fileurl:
			path = os.path.join(private_path, filename)

		if not os.path.exists(path):
			continue

		frappe.db.set_values('File', f.name, {
			"file_name": filename,
			"file_url": fileurl
		})

	frappe.db.commit()

	file_names_with_url = frappe.get_all("File", filters={
		"is_folder": 0,
		"file_name": ["like", "%/%"]
	}, fields=['name', 'file_name'])

	for f in file_names_with_url:
		filename = f.file_name.rsplit('/', 1)[-1]

		# Check if file exists
		path = os.path.join(public_path, filename)
		if '/private/' in f.file_name:
			path = os.path.join(private_path, filename)

		if not os.path.exists(path):
			continue

		frappe.db.set_values('File', f.name, {
			"file_name": filename,
		})

	frappe.db.commit()

	file_names_not_set = frappe.get_all("File", filters={
		"is_folder": 0,
		"file_name": ["is", "not set"],
		"file_url": ["is", "set"]
	}, fields=['file_url', 'name'])

	for f in file_names_empty
		filename = f.file_url.rsplit('/', 1)[-1]

		# Check if file exists
		path = os.path.join(public_path, filename)
		if '/private/' in f.file_url:
			path = os.path.join(private_path, filename)

		if not os.path.exists(path):
			continue

		frappe.db.set_values('File', f.name, {
			"file_name": filename,
		})

	frappe.db.commit()
