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
		"payment_gateway": "Razorpay",
		"subscription_details": {
			"plan_id": "plan_12313", # if Required
			"start_date": "2018-08-30",
			"billing_period": "Month" #(Day, Week, SemiMonth, Month, Year),
			"billing_frequency": 1,
			"customer_notify": 1,
			"upfront_amount": 1000
		}
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
import pytz
from frappe import _
from six.moves.urllib.parse import urlencode
from frappe.model.document import Document
from frappe.integrations.utils import create_request_log, make_post_request, create_payment_gateway
from frappe.utils import get_url, call_hook_method, cint, get_datetime


api_path = '/api/method/frappe.integrations.doctype.paypal_settings.paypal_settings'

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

		response = self.execute_set_express_checkout(**kwargs)

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

	def execute_set_express_checkout(self, **kwargs):
		params, url = self.get_paypal_params_and_url()

		params.update({
			"METHOD": "SetExpressCheckout",
			"returnUrl": get_url("{0}.get_express_checkout_details".format(api_path)),
			"cancelUrl": get_url("/payment-cancel"),
			"PAYMENTREQUEST_0_PAYMENTACTION": "SALE",
			"PAYMENTREQUEST_0_AMT": kwargs['amount'],
			"PAYMENTREQUEST_0_CURRENCYCODE": kwargs['currency'].upper()
		})

		if kwargs.get('subscription_details'):
			self.configure_recurring_payments(params, kwargs)

		params = urlencode(params)
		response = make_post_request(url, data=params.encode("utf-8"))

		if response.get("ACK")[0] != "Success":
			frappe.throw(_("Looks like something is wrong with this site's Paypal configuration."))

		return response

	def configure_recurring_payments(self, params, kwargs):
		# removing the params as we have to setup rucurring payments
		for param in ('PAYMENTREQUEST_0_PAYMENTACTION', 'PAYMENTREQUEST_0_AMT',
			'PAYMENTREQUEST_0_CURRENCYCODE'):
			del params[param]

		params.update({
			"L_BILLINGTYPE0": "RecurringPayments",  #The type of billing agreement
			"L_BILLINGAGREEMENTDESCRIPTION0": kwargs['description']
		})

def get_paypal_and_transaction_details(token):
	doc = frappe.get_doc("PayPal Settings")
	doc.setup_sandbox_env(token)
	params, url = doc.get_paypal_params_and_url()

	integration_request = frappe.get_doc("Integration Request", token)
	data = json.loads(integration_request.data)

	return data, params, url

def setup_redirect(data, redirect_url, custom_redirect_to=None, redirect=True):
	redirect_to = data.get('redirect_to') or None
	redirect_message = data.get('redirect_message') or None

	if custom_redirect_to:
		redirect_to = custom_redirect_to

	if redirect_to:
		redirect_url += '&' + urlencode({'redirect_to': redirect_to})
	if redirect_message:
		redirect_url += '&' + urlencode({'redirect_message': redirect_message})

	# this is done so that functions called via hooks can update flags.redirect_to
	if redirect:
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = get_url(redirect_url)

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

		doc = frappe.get_doc("Integration Request", token)
		update_integration_request_status(token, {
				"payerid": response.get("PAYERID")[0],
				"payer_email": response.get("EMAIL")[0]
			}, "Authorized", doc=doc)

		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = get_redirect_uri(doc, token, response.get("PAYERID")[0])

	except Exception:
		frappe.log_error(frappe.get_traceback())

@frappe.whitelist(allow_guest=True, xss_safe=True)
def confirm_payment(token):
	try:
		custom_redirect_to = None
		data, params, url = get_paypal_and_transaction_details(token)

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
				custom_redirect_to = frappe.get_doc(data.get("reference_doctype"),
					data.get("reference_docname")).run_method("on_payment_authorized", "Completed")
				frappe.db.commit()

			redirect_url = '/integrations/payment-success?doctype={0}&docname={1}'.format(data.get("reference_doctype"), data.get("reference_docname"))
		else:
			redirect_url = "/integrations/payment-failed"

		setup_redirect(data, redirect_url, custom_redirect_to)

	except Exception:
		frappe.log_error(frappe.get_traceback())

@frappe.whitelist(allow_guest=True, xss_safe=True)
def create_recurring_profile(token, payerid):
	try:
		custom_redirect_to = None
		updating = False
		data, params, url = get_paypal_and_transaction_details(token)

		addons = data.get("addons")
		subscription_details = data.get("subscription_details")

		if data.get('subscription_id'):
			if addons:
				updating = True
			manage_recurring_payment_profile_status(data['subscription_id'], 'Cancel', params, url)

		params.update({
			"METHOD": "CreateRecurringPaymentsProfile",
			"PAYERID": payerid,
			"TOKEN": token,
			"DESC": data.get("description"),
			"BILLINGPERIOD": subscription_details.get("billing_period"),
			"BILLINGFREQUENCY": subscription_details.get("billing_frequency"),
			"AMT": data.get("amount") if data.get("subscription_amount") == data.get("amount") else data.get("subscription_amount"),
			"CURRENCYCODE": data.get("currency").upper(),
			"INITAMT": data.get("upfront_amount")
		})

		status_changed_to = 'Completed' if data.get("starting_immediately") or updating else 'Verified'

		starts_at = get_datetime(subscription_details.get("start_date")) or frappe.utils.now_datetime()
		starts_at = starts_at.replace(tzinfo=pytz.timezone(frappe.utils.get_time_zone())).astimezone(pytz.utc)

		#"PROFILESTARTDATE": datetime.utcfromtimestamp(get_timestamp(starts_at)).isoformat()
		params.update({
			"PROFILESTARTDATE": starts_at.isoformat()
		})

		response = make_post_request(url, data=params)

		if response.get("ACK")[0] == "Success":
			update_integration_request_status(token, {
				"profile_id": response.get("PROFILEID")[0],
			}, "Completed")

			if data.get("reference_doctype") and data.get("reference_docname"):
				data['subscription_id'] = response.get("PROFILEID")[0]

				frappe.flags.data = data
				custom_redirect_to = frappe.get_doc(data.get("reference_doctype"),
					data.get("reference_docname")).run_method("on_payment_authorized", status_changed_to)
				frappe.db.commit()

			redirect_url = '/integrations/payment-success?doctype={0}&docname={1}'.format(data.get("reference_doctype"), data.get("reference_docname"))
		else:
			redirect_url = "/integrations/payment-failed"

		setup_redirect(data, redirect_url, custom_redirect_to)

	except Exception:
		frappe.log_error(frappe.get_traceback())

def update_integration_request_status(token, data, status, error=False, doc=None):
	if not doc:
		doc = frappe.get_doc("Integration Request", token)

	doc.update_status(data, status)

def get_redirect_uri(doc, token, payerid):
	data = json.loads(doc.data)

	if data.get("subscription_details") or data.get("subscription_id"):
		return get_url("{0}.create_recurring_profile?token={1}&payerid={2}".format(api_path, token, payerid))
	else:
		return get_url("{0}.confirm_payment?token={1}".format(api_path, token))

def manage_recurring_payment_profile_status(profile_id, action, args, url):
	args.update({
		"METHOD": "ManageRecurringPaymentsProfileStatus",
		"PROFILEID": profile_id,
		"ACTION": action
	})

	response = make_post_request(url, data=args)

	# error code 11556 indicates profile is not in active state(or already cancelled)
	# thus could not cancel the subscription.
	# thus raise an exception only if the error code is not equal to 11556

	if response.get("ACK")[0] != "Success" and response.get("L_ERRORCODE0", [])[0] != '11556':
		frappe.throw(_("Failed while amending subscription"))

@frappe.whitelist(allow_guest=True)
def ipn_handler():
	try:
		data = frappe.local.form_dict

		validate_ipn_request(data)

		data.update({
			"payment_gateway": "PayPal"
		})

		doc = frappe.get_doc({
			"data": json.dumps(frappe.local.form_dict),
			"doctype": "Integration Request",
			"integration_type": "Subscription Notification",
			"status": "Queued"
		}).insert(ignore_permissions=True)
		frappe.db.commit()

		frappe.enqueue(method='frappe.integrations.doctype.paypal_settings.paypal_settings.handle_subscription_notification',
			queue='long', timeout=600, is_async=True, **{"doctype": "Integration Request", "docname":  doc.name})

	except frappe.InvalidStatusError:
		pass
	except Exception as e:
		frappe.log(frappe.log_error(title=e))

def validate_ipn_request(data):
	def _throw():
		frappe.throw(_("In Valid Request"), exc=frappe.InvalidStatusError)

	if not data.get("recurring_payment_id"):
		_throw()

	doc = frappe.get_doc("PayPal Settings")
	params, url = doc.get_paypal_params_and_url()

	params.update({
		"METHOD": "GetRecurringPaymentsProfileDetails",
		"PROFILEID": data.get("recurring_payment_id")
	})

	params = urlencode(params)
	res = make_post_request(url=url, data=params.encode("utf-8"))

	if res['ACK'][0] != 'Success':
		_throw()

def handle_subscription_notification(doctype, docname):
	call_hook_method("handle_subscription_notification", doctype=doctype, docname=docname)
