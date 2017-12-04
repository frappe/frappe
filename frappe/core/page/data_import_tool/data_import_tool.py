# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, print_function

import frappe, os
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
	return frappe.get_user()._get("can_import")

@frappe.whitelist()
def get_doctype_options():
	doctype = frappe.form_dict['doctype']
	return [doctype] + [d.options for d in frappe.get_meta(doctype).get_table_fields()]

def import_file_by_path(path, ignore_links=False, overwrite=False, submit=False, pre_process=None, no_email=True):
	from frappe.utils.csvutils import read_csv_content
	from frappe.core.page.data_import_tool.importer import upload
	print("Importing " + path)
	with open(path, "r") as infile:
		upload(rows = read_csv_content(infile.read()), ignore_links=ignore_links, no_email=no_email, overwrite=overwrite,
            submit_after_import=submit, pre_process=pre_process)

def export_csv(doctype, path):
	from frappe.core.page.data_import_tool.exporter import get_template
	with open(path, "wb") as csvfile:
		get_template(doctype=doctype, all_doctypes="Yes", with_data="Yes")
		csvfile.write(frappe.response.result.encode("utf-8"))

def export_json(doctype, path, filters=None, or_filters=None, name=None):
	def post_process(out):
		del_keys = ('parent', 'parentfield', 'parenttype', 'modified_by', 'creation', 'owner', 'idx')
		for doc in out:
			for key in del_keys:
				if key in doc:
					del doc[key]
			for k, v in doc.items():
				if isinstance(v, list):
					for child in v:
						for key in del_keys + ('docstatus', 'doctype', 'modified', 'name'):
							if key in child:
								del child[key]

	out = []
	if name:
		out.append(frappe.get_doc(doctype, name).as_dict())
	elif frappe.db.get_value("DocType", doctype, "issingle"):
		out.append(frappe.get_doc(doctype).as_dict())
	else:
		for doc in frappe.get_all(doctype, fields=["name"], filters=filters, or_filters=or_filters, limit_page_length=0, order_by="creation asc"):
			out.append(frappe.get_doc(doctype, doc.name).as_dict())
	post_process(out)

	dirname = os.path.dirname(path)
	if not os.path.exists(dirname):
		path = os.path.join('..', path)

	with open(path, "w") as outfile:
		outfile.write(frappe.as_json(out))

@frappe.whitelist()
def export_fixture(doctype, app):
	if frappe.session.user != "Administrator":
		raise frappe.PermissionError

	if not os.path.exists(frappe.get_app_path(app, "fixtures")):
		os.mkdir(frappe.get_app_path(app, "fixtures"))

	export_json(doctype, frappe.get_app_path(app, "fixtures", frappe.scrub(doctype) + ".json"))


def import_doc(path, overwrite=False, ignore_links=False, ignore_insert=False,
    insert=False, submit=False, pre_process=None):
	if os.path.isdir(path):
		files = [os.path.join(path, f) for f in os.listdir(path)]
	else:
		files = [path]

	for f in files:
		if f.endswith(".json"):
			frappe.flags.mute_emails = True
			frappe.modules.import_file.import_file_by_path(f, data_import=True, force=True, pre_process=pre_process, reset_permissions=True)
			frappe.flags.mute_emails = False
			frappe.db.commit()
		elif f.endswith(".csv"):
			import_file_by_path(f, ignore_links=ignore_links, overwrite=overwrite, submit=submit, pre_process=pre_process)
			frappe.db.commit()
