# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import requests
from frappe.model.document import Document
from twilio.rest import Client
from frappe.core.doctype.sms_settings.sms_settings import validate_receiver_nos
from frappe import _
from frappe.utils.print_format import download_pdf

from six import string_types

class TwilioSettings(Document):
	pass

@frappe.whitelist()
def send_whatsapp_message(sender, receiver_list, msg):
	import json
	if isinstance(receiver_list, string_types):
		receiver_list = json.loads(receiver_list)
		if not isinstance(receiver_list, list):
			receiver_list = [receiver_list]


	twilio_settings = frappe.get_doc("Twilio Settings")
	client = Client(twilio_settings.account_sid, twilio_settings.auth_token)
	args = {
		"from_": 'whatsapp:{}'.format(sender),
		"body": msg
	}

	failed_delivery = []

	for rec in receiver_list:
		message_kwargs.update({"to": 'whatsapp:{}'.format(rec)})
		resp = _send_whatsapp(args, client)
		if not resp:
			failed_delivery.append(rec)

	if failed_delivery:
		frappe.log_error(_("The message wasn't correctly delivered to: {}".format(", ".join(failed_delivery))), _('Delivery Failed'))


def _send_whatsapp(message_dict, client):
	try:
		response = client.messages.create(**message_dict)
	except Exception:
		frappe.log_error(response.error, _('Twilio WhatsApp Message Error'))

	return response.sid