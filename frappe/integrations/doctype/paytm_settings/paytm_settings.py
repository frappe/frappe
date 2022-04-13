# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import json

import requests
from paytmchecksum import generateSignature, verifySignature
from six.moves.urllib.parse import urlencode

import frappe
from frappe import _
from frappe.integrations.utils import create_payment_gateway, create_request_log
from frappe.model.document import Document
from frappe.utils import call_hook_method, cint, cstr, flt, get_request_site_address, get_url
from frappe.utils.password import get_decrypted_password


class PaytmSettings(Document):
	supported_currencies = ["INR"]

	def validate(self):
		create_payment_gateway("Paytm")
		call_hook_method("payment_gateway_enabled", gateway="Paytm")

	def validate_transaction_currency(self, currency):
		if currency not in self.supported_currencies:
			frappe.throw(
				_(
					"Please select another payment method. Paytm does not support transactions in currency '{0}'"
				).format(currency)
			)

	def get_payment_url(self, **kwargs):
		"""Return payment url with several params"""
		# create unique order id by making it equal to the integration request
		integration_request = create_request_log(kwargs, "Host", "Paytm")
		kwargs.update(dict(order_id=integration_request.name))

		return get_url("./integrations/paytm_checkout?{0}".format(urlencode(kwargs)))


def get_paytm_config():
	"""Returns paytm config"""

	paytm_config = frappe.db.get_singles_dict("Paytm Settings")
	paytm_config.update(
		dict(merchant_key=get_decrypted_password("Paytm Settings", "Paytm Settings", "merchant_key"))
	)

	if cint(paytm_config.staging):
		paytm_config.update(
			dict(
				website="WEBSTAGING",
				url="https://securegw-stage.paytm.in/order/process",
				transaction_status_url="https://securegw-stage.paytm.in/order/status",
				industry_type_id="RETAIL",
			)
		)
	else:
		paytm_config.update(
			dict(
				url="https://securegw.paytm.in/order/process",
				transaction_status_url="https://securegw.paytm.in/order/status",
			)
		)
	return paytm_config


def get_paytm_params(payment_details, order_id, paytm_config):

	# initialize a dictionary
	paytm_params = dict()

	redirect_uri = (
		get_request_site_address(True)
		+ "/api/method/frappe.integrations.doctype.paytm_settings.paytm_settings.verify_transaction"
	)

	paytm_params.update(
		{
			"MID": paytm_config.merchant_id,
			"WEBSITE": paytm_config.website,
			"INDUSTRY_TYPE_ID": paytm_config.industry_type_id,
			"CHANNEL_ID": "WEB",
			"ORDER_ID": order_id,
			"CUST_ID": payment_details["payer_email"],
			"EMAIL": payment_details["payer_email"],
			"TXN_AMOUNT": cstr(flt(payment_details["amount"], 2)),
			"CALLBACK_URL": redirect_uri,
		}
	)

	checksum = generateSignature(paytm_params, paytm_config.merchant_key)

	paytm_params.update({"CHECKSUMHASH": checksum})

	return paytm_params


@frappe.whitelist(allow_guest=True)
def verify_transaction(**paytm_params):
	"""Verify checksum for received data in the callback and then verify the transaction"""
	paytm_config = get_paytm_config()
	is_valid_checksum = False

	paytm_params.pop("cmd", None)
	paytm_checksum = paytm_params.pop("CHECKSUMHASH", None)

	if paytm_params and paytm_config and paytm_checksum:
		# Verify checksum
		is_valid_checksum = verifySignature(paytm_params, paytm_config.merchant_key, paytm_checksum)

	if is_valid_checksum and paytm_params.get("RESPCODE") == "01":
		verify_transaction_status(paytm_config, paytm_params["ORDERID"])
	else:
		frappe.respond_as_web_page(
			"Payment Failed",
			"Transaction failed to complete. In case of any deductions, deducted amount will get refunded to your account.",
			http_status_code=401,
			indicator_color="red",
		)
		frappe.log_error(
			"Order unsuccessful. Failed Response:" + cstr(paytm_params), "Paytm Payment Failed"
		)


def verify_transaction_status(paytm_config, order_id):
	"""Verify transaction completion after checksum has been verified"""
	paytm_params = dict(MID=paytm_config.merchant_id, ORDERID=order_id)

	checksum = generateSignature(paytm_params, paytm_config.merchant_key)
	paytm_params["CHECKSUMHASH"] = checksum

	post_data = json.dumps(paytm_params)
	url = paytm_config.transaction_status_url

	response = requests.post(url, data=post_data, headers={"Content-type": "application/json"}).json()
	finalize_request(order_id, response)


def finalize_request(order_id, transaction_response):
	request = frappe.get_doc("Integration Request", order_id)
	transaction_data = frappe._dict(json.loads(request.data))
	redirect_to = transaction_data.get("redirect_to") or None
	redirect_message = transaction_data.get("redirect_message") or None

	if transaction_response["STATUS"] == "TXN_SUCCESS":
		if transaction_data.reference_doctype and transaction_data.reference_docname:
			custom_redirect_to = None
			try:
				custom_redirect_to = frappe.get_doc(
					transaction_data.reference_doctype, transaction_data.reference_docname
				).run_method("on_payment_authorized", "Completed")
				request.db_set("status", "Completed")
			except Exception:
				request.db_set("status", "Failed")
				frappe.log_error(frappe.get_traceback())

			if custom_redirect_to:
				redirect_to = custom_redirect_to

			redirect_url = "/integrations/payment-success"
	else:
		request.db_set("status", "Failed")
		redirect_url = "/integrations/payment-failed"

	if redirect_to:
		redirect_url += "?" + urlencode({"redirect_to": redirect_to})
	if redirect_message:
		redirect_url += "&" + urlencode({"redirect_message": redirect_message})

	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = redirect_url


def get_gateway_controller(doctype, docname):
	reference_doc = frappe.get_doc(doctype, docname)
	gateway_controller = frappe.db.get_value(
		"Payment Gateway", reference_doc.payment_gateway, "gateway_controller"
	)
	return gateway_controller
