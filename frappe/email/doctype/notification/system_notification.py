import json

import frappe
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from frappe.utils.jinja import validate_template

from .email import get_list_of_recipients


def validate(self):
	validate_template(self.subject)
	validate_template(self.message)


def send(self, doc, context):
	subject = self.subject
	if "{" in subject:
		subject = frappe.render_template(self.subject, context)

	attachments = self.get_attachment(doc)

	recipients, cc, bcc = get_list_of_recipients(self, doc, context)

	users = recipients + cc + bcc

	if not users:
		return

	notification_doc = {
		"type": "Alert",
		"document_type": doc.doctype,
		"document_name": doc.name,
		"subject": subject,
		"from_user": doc.modified_by or doc.owner,
		"email_content": frappe.render_template(self.message, context),
		"attached_file": attachments and json.dumps(attachments[0]),
	}
	enqueue_create_notification(users, notification_doc)
