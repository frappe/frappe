from typing import TYPE_CHECKING

import frappe
from frappe import _
from frappe.communications.interfaces import NotificationHandler, OutgoingCommunicationHandler
from frappe.core.doctype.role.role import get_info_based_on_role
from frappe.utils import validate_email_address

if TYPE_CHECKING:
	from frappe.communications.doctype.communication.communication import Communication
	from frappe.communications.doctype.notification.notification import Notification
	from frappe.model.document import Document


def get_assignees(doc):
	assignees = []
	assignees = frappe.get_all(
		"ToDo",
		filters={"status": "Open", "reference_name": doc.name, "reference_type": doc.doctype},
		fields=["allocated_to"],
	)

	return [d.allocated_to for d in assignees]


def get_emails_from_template(template, context):
	if not template:
		return ()

	emails = frappe.render_template(template, context) if "{" in template else template
	return filter(None, emails.replace(",", "\n").split("\n"))


def get_list_of_recipients(self, doc, context):
	recipients = []
	cc = []
	bcc = []
	for recipient in self.recipients:
		if not recipient.should_receive(context):
			continue
		if recipient.receiver_by_document_field:
			fields = recipient.receiver_by_document_field.split(",")
			# fields from child table
			if len(fields) > 1:
				for d in doc.get(fields[1]):
					email_id = d.get(fields[0])
					if validate_email_address(email_id):
						recipients.append(email_id)
			# field from parent doc
			else:
				email_ids_value = doc.get(fields[0])
				if validate_email_address(email_ids_value):
					email_ids = email_ids_value.replace(",", "\n")
					recipients = recipients + email_ids.split("\n")

		cc.extend(get_emails_from_template(recipient.cc, context))
		bcc.extend(get_emails_from_template(recipient.bcc, context))

		# For sending emails to specified role
		if recipient.receiver_by_role:
			emails = get_info_based_on_role(recipient.receiver_by_role, "email", ignore_permissions=True)

			for email in emails:
				recipients = recipients + email.split("\n")

	if self.send_to_all_assignees:
		recipients = recipients + get_assignees(doc)

	return list(set(recipients)), list(set(cc)), list(set(bcc))


class EmailNotificationHandlerAdapter(OutgoingCommunicationHandler, NotificationHandler):
	"""
	This is an adapter class that implements the outgoing communication and notification handler interfaces.

	It bridges the comms and email modules.
	"""

	_communication_medium = "Email"

	def _validate_communication(self, comm: Communication):
		attachments = []  # TODO
		comm.has_attachment = 1 if attachments else 0
		pass

	def _send_implementation(self, comm: Communication):
		attachments = []  # TODO
		if not comm.get_outgoing_email_account():
			frappe.throw(
				_(
					"Unable to send mail because of a missing email account. Please setup default Email Account from Settings > Email Account"
				),
				exc=frappe.OutgoingEmailError,
			)
		comm.send_email(
			print_html=None,
			print_format=None,
			send_me_a_copy=False,
			# TODO: implement attachments via communication
			print_letterhead=((attachments and attachments[0].get("print_letterhead")) or False),
		)

		return comm.recipients

	def _get_notification_recipients(
		self, notification: Notification, doc: Document, context: dict
	) -> tuple(list[str], list[str], list[str]):
		"""return receiver list based on the doc field and role specified"""
		recipients, cc, bcc = get_list_of_recipients(notification, doc, context)
		return recipients, cc, bcc

	def _get_notification_sender(
		self, notification: Notification, doc: Document, context: dict
	) -> str:
		from email.utils import formataddr

		sender = None
		if notification.sender and notification.sender_email:
			sender = formataddr((self.sender, self.sender_email))

		return sender
