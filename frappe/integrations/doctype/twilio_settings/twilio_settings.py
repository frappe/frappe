# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils.password import get_decrypted_password

from six import string_types
import re
from json import dumps

from twilio.rest import Client
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from twilio.twiml.voice_response import VoiceResponse, Dial
from frappe.website.render import build_response

class TwilioSettings(Document):
	def on_update(self):
		client = Client(self.account_sid, self.get_password("auth_token"))
		self.validate_twilio_credentials(client)
		self.generate_api_credentials(client)

	def validate_twilio_credentials(self, client):
		try:
			client.api.accounts(self.account_sid).fetch()
		except Exception:
			frappe.throw(_("Invalid Account SID or Auth Token."))

	def generate_api_credentials(self, client):
		if self.api_key and api_secret:
			return

		try:
			credential = client.new_keys.create(friendly_name='Frappe')
			self.api_key = credential.sid
			self.api_secret = credential.secret
		except Exception:
			frappe.throw(_("Twilio API credential creation error."))

def send_whatsapp_message(sender, receiver_list, message):
	import json
	if isinstance(receiver_list, string_types):
		receiver_list = json.loads(receiver_list)
		if not isinstance(receiver_list, list):
			receiver_list = [receiver_list]


	twilio_settings = frappe.get_doc("Twilio Settings")
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

@frappe.whitelist()
def generate_access_token():

	twilio_settings = frappe.get_doc("Twilio Settings")
	# get credentials for environment variables
	account_sid = twilio_settings.account_sid
	application_sid = twilio_settings.get_password("auth_token")
	api_key = twilio_settings.api_key
	api_secret = twilio_settings.get_password("api_secret")

	# Generate a random user name
	identity = "Sample User"
	
	# Create access token with credentials
	token = AccessToken(account_sid, api_key, api_secret, identity=identity)

	# Create a Voice grant and add to token
	voice_grant = VoiceGrant(
		outgoing_application_sid=application_sid,
		incoming_allow=True,
	)
	token.add_grant(voice_grant)

	# Return token info as JSON
	token=token.to_jwt()

	return json.dumps(token)

@frappe.whitelist(allow_guest=True)
def voice(**kwargs):
	frappe.logger().debug(kwargs)
	try:
		args = frappe._dict(kwargs)
		phone_pattern = re.compile(r"^[\d\+\-\(\) ]+$")
		resp = VoiceResponse()
		if args.To != '':
			phone = args.To
			dial = Dial(caller_id="+1 202 953 4504")
			# wrap the phone number or client name in the appropriate TwiML verb
			# by checking if the number given has only digits and format symbols
			if phone_pattern.match(phone):
				dial.number(phone)
			else:
				dial.client(phone)
			resp.append(dial)
		else:
			resp.say("Thanks for calling!")

		return build_response('', str(resp), 200, headers = {"Content-Type": "text/xml; charset=utf-8"})
	except Exception:
		frappe.log_error("Twilio call Error")