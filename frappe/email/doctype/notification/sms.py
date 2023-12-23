import frappe
from frappe.core.doctype.communication.email import _make as make_communication
from frappe.core.doctype.role.role import get_info_based_on_role, get_user_info
from frappe.core.doctype.sms_settings.sms_settings import send_sms
from frappe.utils.jinja import validate_template


def validate(self):
	validate_template(self.message)


def get_receiver_list(self, doc, context):
	"""return receiver list based on the doc field and role specified"""
	receiver_list = []
	for recipient in self.recipients:
		if not recipient.should_receive(context):
			continue

		# For sending messages to the owner's mobile phone number
		if recipient.receiver_by_document_field == "owner":
			receiver_list += get_user_info([dict(user_name=doc.get("owner"))], "mobile_no")
		# For sending messages to the number specified in the receiver field
		elif recipient.receiver_by_document_field:
			receiver_list.append(doc.get(recipient.receiver_by_document_field))

		# For sending messages to specified role
		if recipient.receiver_by_role:
			receiver_list += get_info_based_on_role(recipient.receiver_by_role, "mobile_no")

	return receiver_list


def send(self, doc, context):
	msg = frappe.utils.strip_html_tags(frappe.render_template(self.message, context))
	receiver_list = (get_receiver_list(self, doc, context),)

	# Add sms notification to communication list
	# No need to add if it is already a communication.
	if doc.doctype != "Communication":
		communication = make_communication(
			doctype=doc.doctype,
			name=doc.name,
			content=msg,
			subject="SMS Notification",
			recipients=receiver_list,
			communication_medium="SMS",
			communication_type="Automated Message",
		)
	send_sms(
		receiver_list=receiver_list,
		msg=msg,
	)
