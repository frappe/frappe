import frappe
import os

def execute():
	files = frappe.get_all(
		'File',
		fields = ['name', 'file_name', 'file_url'],
		filters = {
			'is_folder': 0,
			'file_url': ['!=', '']
		}
	)

	for file in files:
		file_name = file.file_url.split('/')[-1]
		private_file_path = frappe.get_site_path('private', 'files')
		public_file_path = frappe.get_site_path('public', 'files')

		file_path = file.file_url or file.file_name
		if '/' not in file_path:
			file_path = '/files/' + file_path

		full_path = get_full_path(file_path)

		if not os.path.exists(full_path):
			if file_path.startswith('/private/files/'):
				public_file_url = os.path.join(public_file_path, file_name)
				if os.path.exists(public_file_url):
					frappe.db.set_value(
						'File',
						file.name,
						{
							'file_url': '/files/{0}'.format(file_name),
							'is_private': 0
						},
						update_modified=False
					)

			elif file_path.startswith('/files/'):
				private_file_url = os.path.join(private_file_path, file_name)
				if os.path.exists(private_file_url):
					frappe.db.set_value(
						'File',
						file.name,
						{
							'file_url': '/private/files/{0}'.format(file_name),
							'is_private': 1
						},
						update_modified=False
					)

def get_full_path(file_path):
	if file_path.startswith("/private/files/"):
		file_path = frappe.utils.get_files_path(*file_path.split("/private/files/", 1)[1].split("/"), is_private=1)

	elif file_path.startswith("/files/"):
		file_path = frappe.utils.get_files_path(*file_path.split("/files/", 1)[1].split("/"))

	else:
		pass

	return file_path
