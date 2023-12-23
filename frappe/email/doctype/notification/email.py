import frappe
from frappe.core.doctype.communication.email import _make as make_communication
from frappe.core.doctype.role.role import get_info_based_on_role
from frappe.utils import validate_email_address
from frappe.utils.jinja import validate_template


def validate(self):
	validate_template(self.subject)
	validate_template(self.message)


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


def send(self, doc, context):
	from email.utils import formataddr

	subject = self.subject
	if "{" in subject:
		subject = frappe.render_template(self.subject, context)

	attachments = self.get_attachment(doc)
	recipients, cc, bcc = get_list_of_recipients(self, doc, context)
	if not (recipients or cc or bcc):
		return

	sender = None
	message = frappe.render_template(self.message, context)
	if self.sender and self.sender_email:
		sender = formataddr((self.sender, self.sender_email))

	communication = None
	# Add mail notification to communication list
	# No need to add if it is already a communication.
	if doc.doctype != "Communication":
		communication = make_communication(
			doctype=doc.doctype,
			name=doc.name,
			content=message,
			subject=subject,
			sender=sender,
			recipients=recipients,
			communication_medium="Email",
			send_email=False,
			attachments=attachments,
			cc=cc,
			bcc=bcc,
			communication_type="Automated Message",
		).get("name")

	frappe.sendmail(
		recipients=recipients,
		subject=subject,
		sender=sender,
		cc=cc,
		bcc=bcc,
		message=message,
		reference_doctype=doc.doctype,
		reference_name=doc.name,
		attachments=attachments,
		expose_recipients="header",
		print_letterhead=((attachments and attachments[0].get("print_letterhead")) or False),
		communication=communication,
	)
