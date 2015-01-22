# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe, json, os
from frappe import _
import frappe.modules.import_file

@frappe.whitelist()
def get_data_keys():
    return frappe._dict({
        "data_separator": _('Start entering data below this line'),
        "main_table": _("Table") + ":",
        "parent_table": _("Parent Table") + ":",
        "columns": _("Column Name") + ":",
        "doctype": _("DocType") + ":"
    })

@frappe.whitelist()
def get_doctypes():
	if "System Manager" in frappe.get_roles():
	    return [r[0] for r in frappe.db.sql("""select name from `tabDocType`
			where allow_import = 1""")]
	else:
		return frappe.user._get("can_import")

@frappe.whitelist()
def get_doctype_options():
	doctype = frappe.form_dict['doctype']
	return [doctype] + [d.options for d in frappe.get_meta(doctype).get_table_fields()]

def import_file_by_path(path, ignore_links=False, overwrite=False, submit=False):
	from frappe.utils.csvutils import read_csv_content
	from frappe.core.page.data_import_tool.importer import upload
	print "Importing " + path
	with open(path, "r") as infile:
		upload(rows = read_csv_content(infile.read()), ignore_links=ignore_links, overwrite=overwrite, submit_after_import=submit)

def export_csv(doctype, path):
	from frappe.core.page.data_import_tool.exporter import get_template
	with open(path, "w") as csvfile:
		get_template(doctype=doctype, all_doctypes="Yes", with_data="Yes")
		csvfile.write(frappe.response.result.encode("utf-8"))

def export_json(doctype, name, path):
	from frappe.utils.response import json_handler
	if not name or name=="-":
		name = doctype
	with open(path, "w") as outfile:
		doc = frappe.get_doc(doctype, name)
		for d in doc.get_all_children():
			d.set("parent", None)
			d.set("name", None)
			d.set("__islocal", 1)
		outfile.write(json.dumps(doc, default=json_handler, indent=1, sort_keys=True))

@frappe.whitelist()
def export_fixture(doctype, name, app):
	if frappe.session.user != "Administrator":
		raise frappe.PermissionError

	if not os.path.exists(frappe.get_app_path(app, "fixtures")):
		os.mkdir(frappe.get_app_path(app, "fixtures"))

	export_json(doctype, name, frappe.get_app_path(app, "fixtures", frappe.scrub(name) + ".json"))


def import_doc(path, overwrite=False, ignore_links=False, ignore_insert=False, insert=False, submit=False):
	if os.path.isdir(path):
		files = [os.path.join(path, f) for f in os.listdir(path)]
	else:
		files = [path]


	for f in files:
		if f.endswith(".json"):
			frappe.modules.import_file.import_file_by_path(f)
		elif f.endswith(".csv"):
			import_file_by_path(f, ignore_links=ignore_links, overwrite=overwrite, submit=submit)
			frappe.db.commit()
