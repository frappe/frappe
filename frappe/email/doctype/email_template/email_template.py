# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from frappe import _
from frappe.model.document import Document
from frappe.utils.jinja import validate_template
from six import string_types

class EmailTemplate(Document):
	def validate(self):
		validate_template(self.response)
		self.validate_default_email_template()

	def validate_default_email_template(self):
		# check if a doctype already has a default template
		for row in self.defaults:
			default_template = get_default_email_template(row.default_doctype)
			if default_template and default_template != self.name and row.is_default:
				frappe.throw(_("Row #{0}: Document {1} already has a Default Email Template {2}")
					.format(row.idx, frappe.bold(row.default_doctype), frappe.bold(default_template)),
						title=_("Default Exists"))

@frappe.whitelist()
def get_email_template(template_name, doc):
	'''Returns the processed HTML of a email template with the given doc'''
	if isinstance(doc, string_types):
		doc = json.loads(doc)

	email_template = frappe.get_doc("Email Template", template_name)
	return {"subject" : frappe.render_template(email_template.subject, doc),
			"message" : frappe.render_template(email_template.response, doc)}

@frappe.whitelist()
def get_default_email_template(doctype):
	'''Returns default email template of given doctype'''
	return frappe.db.get_value("Email Template Default", {"is_default": 1, "default_doctype": doctype}, "parent")