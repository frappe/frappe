# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
@frappe.whitelist()
def restore(version):
	if not "System Manager" in frappe.get_roles():
		raise frappe.PermissionError
		
	version = frappe.doc("Version", version)
	doclist = json.loads(version.doclist_json)

	# check if renamed
	if doclist[0].get("name") != version.docname:
		doclist[0]["name"] = version.docname
		for d in doclist[1:]:
			d["parent"] = version.docname
	
	doclist[0]["modified"] = frappe.db.get_value(version.ref_doctype, version.docname, "modified")
	
	# overwrite
	frappe.bean(doclist).save()