# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
# Integrating AuthorizeNet

### 1. Validate Currency Support

Example:

	controller().validate_transaction_currency(currency)

### 2. Redirect for payment

Example:

	payment_details = {
		"createTransactionRequest": {
			"merchantAuthentication": {
				"name": "xxxxxxxxxx",
				"transactionKey": "xxxxxxxxxxxx"
			},
			"refId": "123456",
			"transactionRequest": {
				"transactionType": "authCaptureTransaction",
				"amount": "5",
				"payment": {
					"credit_card": {
						"card_number": "XXXX-XXXX-XXXX-XXXX",
						"expiration_date": "YYYY-MM",
						"card_code": "XXX"
					}
				},
				"lineItems": {
					"lineItem": {
						"itemId": "1",
						"name": "vase",
						"description": "Cannes logo",
						"quantity": "18",
						"unitPrice": "45.00"
					}
				}
			}
		}
	}

	# redirect the user to this url
	url = controller().get_payment_url(**payment_details)

### 3. On Completion of Payment

Return payment status after processing the payment

"""
from __future__ import unicode_literals
import frappe
import imp
import json
import os
import sys
import re
from six.moves.urllib.parse import urlencode
from frappe.model.document import Document
from frappe.integrations.utils import create_payment_gateway
from frappe.utils import get_url, call_hook_method
from frappe.utils.password import get_decrypted_password

from authorizenet import apicontractsv1
from authorizenet.apicontrollers import createTransactionController

class AuthorizenetSettings(Document):
	supported_currencies = ["USD","CAD"]

	def validate_transaction_currency(self, currency):
		if currency not in self.supported_currencies:
			frappe.throw(_("Please select another payment method. AuthorizeNet does not support transactions in currency '{0}'").format(currency))
	
	def validate(self):
		create_payment_gateway('Authorizenet')
		call_hook_method('payment_gateway_enabled', gateway="Authorizenet")

	def get_payment_url(self, **kwargs):
		return get_url("./integrations/authorizenet_checkout?{0}".format(urlencode(kwargs)))


@frappe.whitelist()
def charge_credit_card(data, card_number, expiration_date, card_code):
	"""
	Charge a credit card
	"""
	data = json.loads(data)
	data = frappe._dict(data)

	# Create a merchantAuthenticationType object with authentication details
	merchant_auth = apicontractsv1.merchantAuthenticationType()
	merchant_auth.name = frappe.db.get_value("Authorizenet Settings", "Authorizenet Settings", ["api_login_id"])
	merchant_auth.transactionKey = get_decrypted_password('Authorizenet Settings', 'Authorizenet Settings',fieldname='api_transaction_key', raise_exception=False)
	
	# Create the payment data for a credit card
	credit_card = apicontractsv1.creditCardType()
	credit_card.cardNumber = card_number
	credit_card.expirationDate = expiration_date
	credit_card.cardCode = card_code

	# Add the payment data to a paymentType object
	payment = apicontractsv1.paymentType()
	payment.creditCard = credit_card

	pr = frappe.get_doc("Payment Request", data.reference_docname)
	sales_order = frappe.get_doc("Sales Order", pr.reference_name).as_dict()

	customer_address = apicontractsv1.customerAddressType()
	customer_address.firstName = data.payer_name
	customer_address.address = sales_order.customer_address[:60]

	# Create order information 
	order = apicontractsv1.orderType()
	order.invoiceNumber = sales_order.name

	for item in sales_order.get("items"):
		for i in range(len(sales_order.get("items"))):

			# setup individual line items
			item[i] = apicontractsv1.lineItemType()
			item[i].itemId = item.item_code
			item[i].name = item.item_name[:30]
			item[i].description = item.item_name
			item[i].quantity = item.qty
			item[i].unitPrice = item.amount

			# build the array of line items
			line_items = apicontractsv1.ArrayOfLineItem()
			line_items.lineItem.append(item[i])

	# Create a transactionRequestType object and add the previous objects to it.
	transaction_request = apicontractsv1.transactionRequestType()
	transaction_request.transactionType = "authCaptureTransaction"
	transaction_request.amount = data.amount
	transaction_request.payment = payment
	transaction_request.order = order
	transaction_request.billTo = customer_address
	transaction_request.lineItems = line_items

	# Assemble the complete transaction request
	create_transaction_request = apicontractsv1.createTransactionRequest()
	create_transaction_request.merchantAuthentication = merchant_auth
	create_transaction_request.transactionRequest = transaction_request

	# Create the controller
	createtransactioncontroller = createTransactionController(
		create_transaction_request)
	createtransactioncontroller.execute()

	response = createtransactioncontroller.getresponse()

	if response is not None:
		# Check to see if the API request was successfully received and acted upon
		if response.messages.resultCode == "Ok":
			# Since the API request was successful, look for a transaction response
			# and parse it to display the results of authorizing the card
			if hasattr(response.transactionResponse, 'messages') is True:
				status = "Completed"
			else:
				status = "Failed"
				if hasattr(response.transactionResponse, 'errors') is True:
					status = "Failed"

		# Or, print errors if the API request wasn't successful
		else:
			status = "Failed"
			if hasattr(response, 'transactionResponse') is True and hasattr(
					response.transactionResponse, 'errors') is True:
				status = "Failed"

			else:
				status = "Failed"

	custom_redirect_to = None

	if status != "Failed":
		try:
			custom_redirect_to = frappe.get_doc(data.reference_doctype, data.reference_docname).run_method("on_payment_authorized",
				status)
		except Exception as ex:
			raise ex

	response = to_dict(response)
	if status == "Completed":
		transId = response.get("transactionResponse").get("transId")
		responseCode = response.get("transactionResponse").get("responseCode")
		code = response.get("transactionResponse").get("messages").get("message").get("code")
		description = response.get("transactionResponse").get("messages").get("message").get("description")
	elif status == "Failed":
		transId = response.get("transactionResponse").get("transId")
		responseCode = response.get("transactionResponse").get("responseCode")
		code = response.get("transactionResponse").get("errors").get("error").get("errorCode")
		description = response.get("transactionResponse").get("errors").get("error").get("errorText")

	return frappe._dict({
		"status": status,
		"transId" : transId,
		"responseCode" : responseCode,
		"code" : code,
		"description" : description
	})

def to_dict(response):
	response_dict = {}
	if response.getchildren() == []:
		return response.text
	else:
		for elem in response.getchildren():
			subdict = to_dict(elem)
			response_dict[re.sub('{.*}', '', elem.tag)] = subdict
	return response_dict