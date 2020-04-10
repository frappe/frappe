# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt
from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt, cint
import json
from six import string_types
from frappe.integrations.doctype.paytm_settings.checksum import generate_checksum_by_str
from frappe.utils import get_request_site_address
import requests

no_cache = 1

expected_keys = ('amount', 'title', 'description', 'reference_doctype', 'reference_docname',
	'payer_name', 'payer_email')

def get_context(context):
	context.no_cache = 1
	merchant_id, merchant_key = get_paytm_credentials()

	try:
		doc = frappe.get_doc("Integration Request", frappe.form_dict['order_id'])
		payment_details = json.loads(doc.data)
		context.token = generate_transaction_token(payment_details, doc.name, merchant_id, merchant_key)
		context.order_id = doc.name


		for key in expected_keys:
			context[key] = payment_details[key]

		context['amount'] = flt(context['amount'], 2)
		context.host = 'https://securegw-stage.paytm.in'
		context.mid = merchant_id

	except Exception as e:
		frappe.log_error()
		frappe.redirect_to_message(_('Invalid Token'),
			_('Seems token you are using is invalid!'),
			http_status_code=400, indicator_color='red')

		frappe.local.flags.redirect_location = frappe.local.response.location
		raise frappe.Redirect

def get_paytm_credentials():
	return frappe.db.get_value("Paytm Settings", None, ['merchant_id', 'merchant_key'])

@frappe.whitelist(allow_guest=True)
def make_payment(paytm_payment_id, options, reference_doctype, reference_docname, token):
	data = {}

	if isinstance(options, string_types):
		data = json.loads(options)

	data.update({
		"paytm_payment_id": paytm_payment_id,
		"reference_docname": reference_docname,
		"reference_doctype": reference_doctype,
		"token": token
	})

	data =  frappe.get_doc("Paytm Settings").create_request(data)
	frappe.db.commit()
	return data

def generate_transaction_token(payment_details, order_id, merchant_id, merchant_key):

	# initialize a dictionary
	paytmParams = dict()

	redirect_uri = get_request_site_address(True) + "?cmd=frappe.templates.pages.integrations.paytm_checkout.get_transaction_status"

	# body parameters
	paytmParams["body"] = {
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

	checksum = generate_checksum_by_str(json.dumps(paytmParams["body"]), merchant_key)

	paytmParams["head"] = {
		"signature"  : checksum
	}

	print(paytmParams)
	post_data = json.dumps(paytmParams)

	url = "https://securegw-stage.paytm.in/theia/api/v1/initiateTransaction?mid={0}&orderId={1}".format(merchant_id, order_id)

	response = requests.post(url, data = post_data, headers = {"Content-type": "application/json"}).json()
	return response['body'].get('txnToken')

@frappe.whitelist(allow_guest=True)
def get_transaction_status():
	print(vars(frappe.form_dict))