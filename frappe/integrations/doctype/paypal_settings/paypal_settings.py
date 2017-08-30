# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

"""
# Integrating PayPal

### 1. Validate Currency Support

Example:

	from frappe.integrations.utils import get_payment_gateway_controller

	controller = get_payment_gateway_controller("PayPal")
	controller().validate_transaction_currency(currency)

### 2. Redirect for payment

Example:

	payment_details = {
		"amount": 600,
		"title": "Payment for bill : 111",
		"description": "payment via cart",
		"reference_doctype": "Payment Request",
		"reference_docname": "PR0001",
		"payer_email": "NuranVerkleij@example.com",
		"payer_name": "Nuran Verkleij",
		"order_id": "111",
		"currency": "USD",
		"payment_gateway": "Razorpay"
	}

	# redirect the user to this url
	url = controller().get_payment_url(**payment_details)


### 3. On Completion of Payment

Write a method for `on_payment_authorized` in the reference doctype

Example:

	def on_payment_authorized(payment_status):
		# your code to handle callback

##### Note:

payment_status - payment gateway will put payment status on callback.
For paypal payment status parameter is one from: [Completed, Cancelled, Failed]


More Details:
<div class="small">For details on how to get your API credentials, follow this link: <a href="https://developer.paypal.com/docs/classic/api/apiCredentials/" target="_blank">https://developer.paypal.com/docs/classic/api/apiCredentials/</a></div>

"""

from __future__ import unicode_literals
import frappe
import json
from frappe import _
from frappe.utils import get_url, call_hook_method, cint
from six.moves.urllib.parse import urlencode
from frappe.model.document import Document
from frappe.integrations.utils import create_request_log, make_post_request, create_payment_gateway

class PayPalSettings(Document):
	supported_currencies = ["AUD", "BRL", "CAD", "CZK", "DKK", "EUR", "HKD", "HUF", "ILS", "JPY", "MYR", "MXN",
		"TWD", "NZD", "NOK", "PHP", "PLN", "GBP", "RUB", "SGD", "SEK", "CHF", "THB", "TRY", "USD"]

	def __setup__(self):
		setattr(self, "use_sandbox", 0)

	def setup_sandbox_env(self, token):
		data = json.loads(frappe.db.get_value("Integration Request", token, "data"))
		setattr(self, "use_sandbox", cint(frappe._dict(data).use_sandbox) or 0)

	def validate(self):
		create_payment_gateway("PayPal")
		call_hook_method('payment_gateway_enabled', gateway="PayPal")
		if not self.flags.ignore_mandatory:
			self.validate_paypal_credentails()

	def on_update(self):
		pass

	def validate_transaction_currency(self, currency):
		if currency not in self.supported_currencies:
			frappe.throw(_("Please select another payment method. PayPal does not support transactions in currency '{0}'").format(currency))

	def get_paypal_params_and_url(self):
		params = {
			"USER": self.api_username,
			"PWD": self.get_password(fieldname="api_password", raise_exception=False),
			"SIGNATURE": self.signature,
			"VERSION": "98",
			"METHOD": "GetPalDetails"
		}

		if hasattr(self, "use_sandbox") and self.use_sandbox:
			params.update({
				"USER": frappe.conf.sandbox_api_username,
				"PWD": frappe.conf.sandbox_api_password,
				"SIGNATURE": frappe.conf.sandbox_signature
			})

		api_url = "https://api-3t.sandbox.paypal.com/nvp" if (self.paypal_sandbox or self.use_sandbox) else "https://api-3t.paypal.com/nvp"

		return params, api_url

	def validate_paypal_credentails(self):
		params, url = self.get_paypal_params_and_url()
		params = urlencode(params)

		try:
			res = make_post_request(url=url, data=params.encode("utf-8"))

			if res["ACK"][0] == "Failure":
				raise Exception

		except Exception:
			frappe.throw(_("Invalid payment gateway credentials"))

	def get_payment_url(self, **kwargs):
		setattr(self, "use_sandbox", cint(kwargs.get("use_sandbox", 0)))

		response = self.execute_set_express_checkout(kwargs["amount"], kwargs["currency"])

		if self.paypal_sandbox or self.use_sandbox:
			return_url = "https://www.sandbox.paypal.com/cgi-bin/webscr?cmd=_express-checkout&token={0}"
		else:
			return_url = "https://www.paypal.com/cgi-bin/webscr?cmd=_express-checkout&token={0}"

		kwargs.update({
			"token": response.get("TOKEN")[0],
			"correlation_id": response.get("CORRELATIONID")[0]
		})

		self.integration_request = create_request_log(kwargs, "Remote", "PayPal", response.get("TOKEN")[0])

		return return_url.format(kwargs["token"])

	def execute_set_express_checkout(self, amount, currency):
		params, url = self.get_paypal_params_and_url()
		params.update({
			"METHOD": "SetExpressCheckout",
			"PAYMENTREQUEST_0_PAYMENTACTION": "SALE",
			"PAYMENTREQUEST_0_AMT": amount,
			"PAYMENTREQUEST_0_CURRENCYCODE": currency.upper(),
			"returnUrl": get_url("/api/method/frappe.integrations.doctype.paypal_settings.paypal_settings.get_express_checkout_details"),
			"cancelUrl": get_url("/payment-cancel")
		})

		params = urlencode(params)

		response = make_post_request(url, data=params.encode("utf-8"))
		if response.get("ACK")[0] != "Success":
			frappe.throw(_("Looks like something is wrong with this site's Paypal configuration."))

		return response

@frappe.whitelist(allow_guest=True, xss_safe=True)
def get_express_checkout_details(token):
	try:
		doc = frappe.get_doc("PayPal Settings")
		doc.setup_sandbox_env(token)

		params, url = doc.get_paypal_params_and_url()
		params.update({
			"METHOD": "GetExpressCheckoutDetails",
			"TOKEN": token
		})

		response = make_post_request(url, data=params)

		if response.get("ACK")[0] != "Success":
			frappe.respond_as_web_page(_("Something went wrong"),
				_("Looks like something went wrong during the transaction. Since we haven't confirmed the payment, Paypal will automatically refund you this amount. If it doesn't, please send us an email and mention the Correlation ID: {0}.").format(response.get("CORRELATIONID", [None])[0]),
				indicator_color='red',
				http_status_code=frappe.ValidationError.http_status_code)

			return

		update_integration_request_status(token, {
				"payerid": response.get("PAYERID")[0],
				"payer_email": response.get("EMAIL")[0]
			}, "Authorized")

		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = get_url( \
			"/api/method/frappe.integrations.doctype.paypal_settings.paypal_settings.confirm_payment?token={0}".format(token))

	except Exception:
		frappe.log_error(frappe.get_traceback())

@frappe.whitelist(allow_guest=True, xss_safe=True)
def confirm_payment(token):
	try:
		redirect = True
		status_changed_to, redirect_to = None, None

		doc = frappe.get_doc("PayPal Settings")
		doc.setup_sandbox_env(token)

		integration_request = frappe.get_doc("Integration Request", token)
		data = json.loads(integration_request.data)

		redirect_to = data.get('redirect_to') or None
		redirect_message = data.get('redirect_message') or None

		params, url = doc.get_paypal_params_and_url()
		params.update({
			"METHOD": "DoExpressCheckoutPayment",
			"PAYERID": data.get("payerid"),
			"TOKEN": token,
			"PAYMENTREQUEST_0_PAYMENTACTION": "SALE",
			"PAYMENTREQUEST_0_AMT": data.get("amount"),
			"PAYMENTREQUEST_0_CURRENCYCODE": data.get("currency").upper()
		})

		response = make_post_request(url, data=params)

		if response.get("ACK")[0] == "Success":
			update_integration_request_status(token, {
				"transaction_id": response.get("PAYMENTINFO_0_TRANSACTIONID")[0],
				"correlation_id": response.get("CORRELATIONID")[0]
			}, "Completed")

			if data.get("reference_doctype") and data.get("reference_docname"):
				redirect_url = frappe.get_doc(data.get("reference_doctype"), data.get("reference_docname")).run_method("on_payment_authorized", "Completed")
				frappe.db.commit()

			if not redirect_url:
				redirect_url = '/integrations/payment-success'
		else:
			redirect_url = "/integrations/payment-failed"

		if redirect_to:
			redirect_url += '?' + urlencode({'redirect_to': redirect_to})
		if redirect_message:
			redirect_url += '&' + urlencode({'redirect_message': redirect_message})

		# this is done so that functions called via hooks can update flags.redirect_to
		if redirect:
			frappe.local.response["type"] = "redirect"
			frappe.local.response["location"] = get_url(redirect_url)

	except Exception:
		frappe.log_error(frappe.get_traceback())

def update_integration_request_status(token, data, status, error=False):
	frappe.get_doc("Integration Request", token).update_status(data, status)
