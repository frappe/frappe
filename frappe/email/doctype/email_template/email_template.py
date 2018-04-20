# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from frappe.model.document import Document
from frappe.utils.jinja import validate_template
from six import string_types

class EmailTemplate(Document):
	def validate(self):
		validate_template(self.response)

@frappe.whitelist()
def get_email_template(template_name, doc):
	'''Returns the processed HTML of a email template with the given doc'''
	if isinstance(doc, string_types):
		doc = json.loads(doc)

	email_template = frappe.get_doc("Email Template", template_name)
	return {"subject" : frappe.render_template(email_template.subject, doc),
			"message" : frappe.render_template(email_template.response, doc)}