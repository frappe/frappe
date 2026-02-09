# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.model.document import Document
from frappe.utils.jinja import validate_template


class EmailTemplate(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		response: DF.TextEditor | None
		response_html: DF.Code | None
		subject: DF.Data
		use_html: DF.Check
	# end: auto-generated types

	@property
	def response_(self):
		return self.response_html if self.use_html else self.response

	def validate(self):
		validate_template(self.subject)
		validate_template(self.response_)

	def get_formatted_subject(self, doc):
		return frappe.render_template(self.subject, doc)

	def get_formatted_response(self, doc):
		return frappe.render_template(self.response_, doc)

	def get_formatted_email(self, doc, sender=None):
		if isinstance(doc, str):
			doc = json.loads(doc)

		if self.use_html:
			doc = self.inject_email_account(doc, sender)

		return {
			"subject": self.get_formatted_subject(doc),
			"message": self.get_formatted_response(doc),
		}

	def inject_email_account(self, doc, sender=None):
		from frappe.email.doctype.email_account.email_account import EmailAccount
		from frappe.email.email_body import get_footer, get_signature

		if sender:
			kwargs = {"match_by_email": sender}
		else:
			kwargs = {"match_by_doctype": doc.get("doctype")}

		if email_account := EmailAccount.find_outgoing(**kwargs):
			doc.update(
				{"email_signature": get_signature(email_account), "email_footer": get_footer(email_account)}
			)
		return doc


@frappe.whitelist()
def get_email_template(template_name, doc, sender=None):
	"""Return the processed HTML of a email template with the given doc"""

	email_template = frappe.get_doc("Email Template", template_name)
	return email_template.get_formatted_email(doc, sender=sender)
