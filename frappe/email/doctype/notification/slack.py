import frappe
from frappe.integrations.doctype.slack_webhook_url.slack_webhook_url import send_slack_message
from frappe.utils.jinja import validate_template


def validate(self):
	validate_template(self.subject)
	validate_template(self.message)


def send(self, doc, context):
	send_slack_message(
		webhook_url=self.slack_webhook_url,
		message=frappe.render_template(self.message, context),
		reference_doctype=doc.doctype,
		reference_name=doc.name,
	)
