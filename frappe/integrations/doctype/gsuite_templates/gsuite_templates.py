# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.integrations.doctype.gsuite_settings.gsuite_settings import run_gsuite_script
from frappe.utils.file_manager import save_url

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

	r = run_gsuite_script('new', filename, templ.template_id, templ.destination_id, json_data)

	filedata = save_url(r['url'], filename, doctype, docname, "Home/Attachments", True)
	comment = frappe.get_doc(doctype, docname).add_comment("Attachment",
		_("added {0}").format("<a href='{file_url}' target='_blank'>{file_name}</a>{icon}".format(**{
			"icon": ' <i class="fa fa-lock text-warning"></i>' if filedata.is_private else "",
			"file_url": filedata.file_url.replace("#", "%23") if filedata.file_name else filedata.file_url,
			"file_name": filedata.file_name or filedata.file_url
		})))

	return {
		"name": filedata.name,
		"file_name": filedata.file_name,
		"file_url": filedata.file_url,
		"is_private": filedata.is_private,
		"comment": comment.as_dict() if comment else {}
		}
