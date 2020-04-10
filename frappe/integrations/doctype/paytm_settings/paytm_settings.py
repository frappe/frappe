# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _
from six.moves.urllib.parse import urlencode
from frappe.utils import get_url, call_hook_method, cint, flt
from frappe.integrations.utils import make_get_request, make_post_request, create_request_log, create_payment_gateway
from frappe.utils import get_request_site_address

import json
import requests

class PaytmSettings(Document):
	supported_currencies = ["INR"]

	def validate(self):
		create_payment_gateway('Paytm')
		call_hook_method('payment_gateway_enabled', gateway='Paytm')
		if not self.flags.ignore_mandatory:
			self.validate_paytm_credentails()

	def validate_paytm_credentails(self):
		if self.merchant_id and self.merchant_key:
			pass
			# header = {"Authorization": "Bearer {0}".format(self.get_password(fieldname="secret_key", raise_exception=False))}
			# try:
			# 	make_get_request(url="https://api.stripe.com/v1/charges", headers=header)
			# except Exception:
			# 	frappe.throw(_("Seems Publishable Key or Secret Key is wrong !!!"))

	def validate_transaction_currency(self, currency):
		if currency not in self.supported_currencies:
			frappe.throw(_("Please select another payment method. Stripe does not support transactions in currency '{0}'").format(currency))

	def get_payment_url(self, **kwargs):
		'''Return payment url with several params'''
		# create unique order id by making it equal to the integration request
		integration_request = create_request_log(kwargs, "Host", "Paytm")
		kwargs.update(dict(order_id=integration_request.name))

		return get_url("./integrations/paytm_checkout?{0}".format(urlencode(kwargs)))

	def create_request(self, data):
		self.data = frappe._dict(data)

		try:
			self.integration_request = create_request_log(self.data, "Host", "Paytm")
			return self.generate_transaction_token()

		except Exception:
			frappe.log_error(frappe.get_traceback())
			return{
				"redirect_to": frappe.redirect_to_message(_('Server Error'), _("It seems that there is an issue with the server's stripe configuration. In case of failure, the amount will get refunded to your account.")),
				"status": 401
			}

	def generate_transaction_token(self):
		import stripe
		try:
			charge = stripe.Charge.create(amount=cint(flt(self.data.amount)*100), currency=self.data.currency, source=self.data.stripe_token_id, description=self.data.description, receipt_email=self.data.payer_email)

			if charge.captured == True:
				self.integration_request.db_set('status', 'Completed', update_modified=False)
				self.flags.status_changed_to = "Completed"

			else:
				frappe.log_error(charge.failure_message, 'Stripe Payment not completed')

		except Exception:
			frappe.log_error(frappe.get_traceback())

		return self.finalize_request()


	def finalize_request(self):
		redirect_to = self.data.get('redirect_to') or None
		redirect_message = self.data.get('redirect_message') or None
		status = self.integration_request.status

		if self.flags.status_changed_to == "Completed":
			if self.data.reference_doctype and self.data.reference_docname:
				custom_redirect_to = None
				try:
					custom_redirect_to = frappe.get_doc(self.data.reference_doctype,
						self.data.reference_docname).run_method("on_payment_authorized", self.flags.status_changed_to)
				except Exception:
					frappe.log_error(frappe.get_traceback())

				if custom_redirect_to:
					redirect_to = custom_redirect_to

				redirect_url = 'payment-success'

			if self.redirect_url:
				redirect_url = self.redirect_url
				redirect_to = None
		else:
			redirect_url = 'payment-failed'

		if redirect_to:
			redirect_url += '?' + urlencode({'redirect_to': redirect_to})
		if redirect_message:
			redirect_url += '&' + urlencode({'redirect_message': redirect_message})

		return {
			"redirect_to": redirect_url,
			"status": status
		}

def generate_transaction_token(payment_details, order_id, merchant_id, merchant_key):

	# initialize a dictionary
	paytmParams = dict()

	redirect_uri = get_request_site_address(True) + "?cmd=frappe.templates.pages.integrations.paytm_checkout.get_transaction_status"

	# body parameters
	paytmParams["body"] = get_paytm_params(payment_details, order_id, merchant_id, merchant_key)

	checksum = generate_checksum_by_str(json.dumps(paytmParams["body"]), merchant_key)

	paytmParams["head"] = {
		"signature"  : checksum
	}

	post_data = json.dumps(paytmParams)

	url = "https://securegw-stage.paytm.in/theia/api/v1/initiateTransaction?mid={0}&orderId={1}".format(merchant_id, order_id)

	response = requests.post(url, data = post_data, headers = {"Content-type": "application/json"}).json()
	return response['body'].get('txnToken')

def get_paytm_params(payment_details, order_id, merchant_id, merchant_key):
	return {
		"requestType" : "Payment",
		"mid" : merchant_id,
		"websiteName" : "WEBSTAGING",
		"orderId" : order_id,
		"callbackUrl" : redirect_uri,
		"txnAmount" : {
			"value" : flt(payment_details['amount'], 2),
			"currency" : "INR",
		},
		"userInfo" : {
			"custId" : payment_details['payer_email'],
		},
	}

def get_gateway_controller(doctype, docname):
	reference_doc = frappe.get_doc(doctype, docname)
	gateway_controller = frappe.db.get_value("Payment Gateway", reference_doc.payment_gateway, "gateway_controller")
	return gateway_controller