# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.integrations.doctype.gsuite_settings.gsuite_settings import run_gsuite_script

class GSuiteTemplates(Document):
	pass

@frappe.whitelist()
def create_gsuite_doc(doctype, docname, gs_template=None):
	templ = frappe.get_doc('GSuite Templates', gs_template)
	doc = frappe.get_doc(doctype, docname)

	if not doc.has_permission("read"):
		raise frappe.PermissionError

	json_data = doc.as_dict()
	filename = templ.document_name.format(**json_data)

	response = run_gsuite_script('new', filename, templ.template_id, templ.destination_id, json_data)

	_file = frappe.get_doc({
		"doctype": "File",
		"file_url": response['url'],
		"file_name": filename,
		"attached_to_doctype": doctype,
		"attached_to_name": docname,
		"attached_to_field": True,
		"folder": "Home/Attachments"})
	_file.save()

	comment = frappe.get_doc(doctype, docname).add_comment("Attachment",
		_("added {0}").format("<a href='{file_url}' target='_blank'>{file_name}</a>{icon}".format(**{
			"icon": ' <i class="fa fa-lock text-warning"></i>' if _file.is_private else "",
			"file_url": _file.file_url.replace("#", "%23") if _file.file_name else _file.file_url,
			"file_name": _file.file_name or _file.file_url
		})))

	return {
		"name": _file.name,
		"file_name": _file.file_name,
		"file_url": _file.file_url,
		"is_private": _file.is_private,
		"comment": comment.as_dict() if comment else {}
		}
