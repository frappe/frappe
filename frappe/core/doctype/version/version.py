# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json

from frappe.model.document import Document

class Version(Document):
	pass
		
@frappe.whitelist()
def restore(version):
	if not "System Manager" in frappe.get_roles():
		raise frappe.PermissionError
		
	version = frappe.get_doc("Version", version)
	docdict = json.loads(version.doclist_json)

	# check if renamed
	if docdict.get("name") != version.docname:
		docdict["name"] = version.docname
	
	docdict["modified"] = frappe.db.get_value(version.ref_doctype, version.docname, "modified")
	
	# overwrite
	frappe.get_doc(docdict).save()