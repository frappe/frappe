from __future__ import print_function, unicode_literals
import frappe

def execute():
	from frappe.core.doctype.file.file import make_home_folder

	if not frappe.db.exists("DocType", "File"):
		frappe.rename_doc("DocType", "File Data", "File")
		frappe.reload_doctype("File")

	if not frappe.db.exists("File", {"is_home_folder": 1}):
		make_home_folder()

	# make missing folders and set parent folder
	for file in frappe.get_all("File", filters={"is_folder": 0}):
		file = frappe.get_doc("File", file.name)
		file.flags.ignore_folder_validate = True
		file.flags.ignore_file_validate = True
		file.flags.ignore_duplicate_entry_error = True
		file.flags.ignore_links = True
		file.set_folder_name()
		try:
			file.save()
		except:
			print(frappe.get_traceback())
			raise

	from frappe.utils.nestedset import rebuild_tree
	rebuild_tree("File", "folder")

	# reset file size
	for folder in frappe.db.sql("""select name from tabFile f1 where is_folder = 1 and
		(select count(*) from tabFile f2 where f2.folder = f1.name and f2.is_folder = 1) = 0"""):
		folder = frappe.get_doc("File", folder[0])
		folder.save()



