# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils.password import get_decrypted_password
from twilio.rest import Client
from six import string_types
from json import loads

class TwilioSettings(Document):
	def on_update(self):
		if self.enabled:
			self.validate_twilio_credentials()

	def validate_twilio_credentials(self):
		try:
			auth_token = get_decrypted_password("Twilio Settings", "Twilio Settings", 'auth_token')
			client = Client(self.account_sid, auth_token)
			client.api.accounts(self.account_sid).fetch()
		except Exception:
			frappe.throw(_("Invalid Account SID or Auth Token."))

def send_whatsapp_message(sender, receiver_list, message):
	twilio_settings = frappe.get_doc("Twilio Settings")
	if not twilio_settings.enabled:
		frappe.throw(_("Please enable twilio settings before sending WhatsApp messages"))

	if isinstance(receiver_list, string_types):
		receiver_list = loads(receiver_list)
		if not isinstance(receiver_list, list):
			receiver_list = [receiver_list]

	auth_token = get_decrypted_password("Twilio Settings", "Twilio Settings", 'auth_token')
	client = Client(twilio_settings.account_sid, auth_token)
	args = {
		"from_": 'whatsapp:+{}'.format(sender),
		"body": message
	}

	failed_delivery = []

	for rec in receiver_list:
		args.update({"to": 'whatsapp:{}'.format(rec)})
		resp = _send_whatsapp(args, client)
		if not resp or resp.error_message:
			failed_delivery.append(rec)

	if failed_delivery:
		frappe.log_error(_("The message wasn't correctly delivered to: {}".format(", ".join(failed_delivery))), _('Delivery Failed'))


def _send_whatsapp(message_dict, client):
	response = frappe._dict()
	try:
		response = client.messages.create(**message_dict)
	except Exception as e:
		frappe.log_error(e, title = _('Twilio WhatsApp Message Error'))

	return response