import frappe


def execute():

	for f in frappe.get_all("File", filters={"is_folder": 0, "file_url": ["is", "not set"], "file_name": ["like", "%/%"]}, fields=['name', 'file_name']):
		fileurl = f.file_name
		filename = f.file_name.rsplit('/', 1)[-1]

		frappe.db.sql('''
		update `tabFile` set file_url = {0}, file_name = {1} where name = {2}
		'''.format(fileurl, filename, f.name))

	frappe.db.commit()

	for f in frappe.get_all("File", filters={"is_folder": 0, "file_name": ["like", "%/%"]}, fields=['name', 'file_name']):
		filename = f.file_name.rsplit('/', 1)[-1]

		frappe.db.sql('''
		update `tabFile` set file_name = {0} where name = {1}
		'''.format(filename, f.name))

	frappe.db.commit()

	for f in frappe.get_all("File", filters={"is_folder": 0, "file_name": ["is", "not set"], "file_url": ["is", "set"]}, fields=['file_url', 'name']):
		filename = f.file_url.rsplit('/', 1)[-1]

		frappe.db.sql('''
		update `tabFile` set file_name = {0} where name = {1}
		'''.format(filename, f.name))

	frappe.db.commit()




