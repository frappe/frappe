import frappe


def execute():
	files = frappe.get_all(
		"File", fields=["is_private", "file_url", "name"], filters={"is_folder": 0}
	)

	for file in files:
		file_url = file.file_url or ""
		if file.is_private:
			if not file_url.startswith("/private/files/"):
				generate_file(file.name)
		else:
			if file_url.startswith("/private/files/"):
				generate_file(file.name)


def generate_file(file_name):
	try:
		file_doc = frappe.get_doc("File", file_name)
		# private
		new_doc = frappe.new_doc("File")
		new_doc.is_private = file_doc.is_private
		new_doc.file_name = file_doc.file_name
		# to create copy of file in right location
		# if the file doc is private then the file will be created in /private folder
		# if the file doc is public then the file will be created in /files folder
		new_doc.save_file(content=file_doc.get_content(), ignore_existing_file_check=True)

		file_doc.file_url = new_doc.file_url
		file_doc.save()
	except IOError:
		pass
	except Exception as e:
		print(e)
