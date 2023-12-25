# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json
from typing import TYPE_CHECKING

import frappe
from frappe import _
from frappe.communications.interfaces import NotificationHandler, OutgoingCommunicationHandler
from frappe.core.doctype.role.role import get_info_based_on_role, get_user_info
from frappe.model.document import Document
from frappe.utils import nowdate

if TYPE_CHECKING:
	from frappe.communications.doctype.communication.communication import Communication
	from frappe.communications.doctype.notification.notification import Notification


class SMSSettings(Document, OutgoingCommunicationHandler, NotificationHandler):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.sms_parameter.sms_parameter import SMSParameter
		from frappe.types import DF

		message_parameter: DF.Data
		parameters: DF.Table[SMSParameter]
		receiver_parameter: DF.Data
		sms_gateway_url: DF.SmallText
		use_post: DF.Check
	# end: auto-generated types

	_communication_medium = "SMS"

	def _validate_communication(self, comm: Communication):
		receiver_list = json.loads(comm.recipients)
		if not isinstance(receiver_list, list):
			receiver_list = [receiver_list]

		comm.recipients = validate_receiver_nos(receiver_list)
		comm.content = frappe.utils.strip_html_tags(comm.content)

	def _send_implementation(self, comm: Communication):
		if not self.sms_gateway_url:
			frappe.throw(_("Please update SMS Settings"))
		successful = send_via_gateway(
			{
				"receiver_list": json.loads(comm.recipients),
				"message": frappe.safe_decode(comm.content).encode("utf-8"),
			}
		)
		return successful

	def _get_notification_recipients(
		self, notification: Notification, doc: Document, context: dict
	) -> list[str]:
		"""return receiver list based on the doc field and role specified"""
		receiver_list = []
		for recipient in notification.recipients:
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

	def _get_notification_sender(
		self, notification: Notification, doc: Document, context: dict
	) -> str:
		return None

	def _log_notification(self, notification: Notification, doc: Document, context: dict) -> bool:
		if doc.docname == "Communication":
			return False  # Don't log a notification from an already existing communication again
		return True


def validate_receiver_nos(receiver_list):
	validated_receiver_list = []
	for d in receiver_list:
		if not d:
			continue

		# remove invalid character
		for x in [" ", "-", "(", ")"]:
			d = d.replace(x, "")

		validated_receiver_list.append(d)

	if not validated_receiver_list:
		frappe.throw(_("Please enter valid mobile nos"))

	return validated_receiver_list


@frappe.whitelist()
def get_contact_number(contact_name, ref_doctype, ref_name):
	"Return mobile number of the given contact."
	number = frappe.db.sql(
		"""select mobile_no, phone from tabContact
		where name=%s
			and exists(
				select name from `tabDynamic Link` where link_doctype=%s and link_name=%s
			)
	""",
		(contact_name, ref_doctype, ref_name),
	)

	return number and (number[0][0] or number[0][1]) or ""


def send_via_gateway(arg):
	ss = frappe.get_doc("SMS Settings", "SMS Settings")
	headers = get_headers(ss)
	use_json = headers.get("Content-Type") == "application/json"

	message = frappe.safe_decode(arg.get("message"))
	args = {ss.message_parameter: message}
	for d in ss.get("parameters"):
		if not d.header:
			args[d.parameter] = d.value

	success_list = []
	for d in arg.get("receiver_list"):
		args[ss.receiver_parameter] = d
		status = send_request(ss.sms_gateway_url, args, headers, ss.use_post, use_json)

		if 200 <= status < 300:
			success_list.append(d)

	if len(success_list) > 0:
		args.update(arg)
		create_sms_log(args, success_list)

	return success_list


def get_headers(sms_settings=None):
	if not sms_settings:
		sms_settings = frappe.get_doc("SMS Settings", "SMS Settings")

	headers = {"Accept": "text/plain, text/html, */*"}
	for d in sms_settings.get("parameters"):
		if d.header == 1:
			headers.update({d.parameter: d.value})

	return headers


def send_request(gateway_url, params, headers=None, use_post=False, use_json=False):
	import requests

	if not headers:
		headers = get_headers()
	kwargs = {"headers": headers}

	if use_json:
		kwargs["json"] = params
	elif use_post:
		kwargs["data"] = params
	else:
		kwargs["params"] = params

	if use_post:
		response = requests.post(gateway_url, **kwargs)
	else:
		response = requests.get(gateway_url, **kwargs)
	response.raise_for_status()
	return response.status_code


# Create SMS Log
# =========================================================
def create_sms_log(args, sent_to):
	sl = frappe.new_doc("SMS Log")
	sl.sent_on = nowdate()
	sl.message = args["message"].decode("utf-8")
	sl.no_of_requested_sms = len(args["receiver_list"])
	sl.requested_numbers = "\n".join(args["receiver_list"])
	sl.no_of_sent_sms = len(sent_to)
	sl.sent_to = "\n".join(sent_to)
	sl.flags.ignore_permissions = True
	sl.save()
