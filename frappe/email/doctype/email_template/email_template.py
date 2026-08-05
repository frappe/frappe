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

	def get_formatted_email(self, doc):
		if isinstance(doc, str):
			doc = json.loads(doc)

		return {
			"subject": self.get_formatted_subject(doc),
			"message": self.get_formatted_response(doc),
		}


@frappe.whitelist()
def get_email_template(template_name, doc):
	"""Returns the processed HTML of a email template with the given doc"""

	email_template = frappe.get_doc("Email Template", template_name)
<<<<<<< HEAD
	return email_template.get_formatted_email(doc)
=======
	email_template.check_permission("read")
	return email_template.get_formatted_email(doc, sender=sender)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_email_templates(
	doctype: str,
	txt: str,
	searchfield: str,
	start: int,
	page_len: int,
	filters: dict,
):
	"""Search for Email Templates scoped to a DocType or with no DocType assigned."""
	reference_doctype = (filters or {}).get("reference_doctype", "")

	return frappe.get_all(
		"Email Template",
		filters={"name": ("like", f"%{txt}%")},
		or_filters=[
			["reference_doctype", "=", reference_doctype],
			["reference_doctype", "is", "not set"],
			["reference_doctype", "=", ""],
		],
		fields=["name", "reference_doctype"],
		limit_start=start,
		limit_page_length=page_len,
		as_list=True,
	)
>>>>>>> 5ecf20421d (fix(email_template): add perm. chk. to get_email_template)
