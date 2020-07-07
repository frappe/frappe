import frappe
import os

def execute():
	files = frappe.get_all('File', filters={'is_folder': 0})
	for file in files:
		doc = frappe.get_doc('File', file.name)
		file_name = doc.file_url.split('/')[-1]
		private_file_path = frappe.get_site_path('private', 'files')
		public_file_path = frappe.get_site_path('public', 'files')

		file_path = doc.file_url or doc.file_name
		if '/' not in file_path:
			file_path = '/files/' + file_path

		full_path = doc.get_full_path()

		if not os.path.exists(full_path):
			if file_path.startswith('/private/files/'):
				public_file_url = os.path.join(public_file_path, file_name)
				if os.path.exists(public_file_url):
					frappe.db.set_value(
						'File',
						doc.name,
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
						doc.name,
						{
							'file_url': '/private/files/{0}'.format(file_name),
							'is_private': 1
						},
						update_modified=False
					)

