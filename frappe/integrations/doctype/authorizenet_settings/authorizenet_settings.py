# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import imp
import json
import os
import sys
from six.moves.urllib.parse import urlencode
from frappe.model.document import Document
from frappe.integrations.utils import create_payment_gateway
from frappe.utils import get_url, call_hook_method
from frappe.utils.password import get_decrypted_password

from authorizenet import apicontractsv1
from authorizenet.apicontrollers import createTransactionController

class AuthorizenetSettings(Document):
	supported_currencies = ["USD"]

	def validate_transaction_currency(self, currency):
		if currency not in self.supported_currencies:
			frappe.throw(_("Please select another payment method. AuthozieNet does not support transactions in currency '{0}'").format(currency))
	
	def validate(self):
		create_payment_gateway('Authorizenet')
		call_hook_method('payment_gateway_enabled', gateway="Authorizenet")

	def get_payment_url(self, **kwargs):
		return get_url("./integrations/authorizenet_checkout?{0}".format(urlencode(kwargs)))


@frappe.whitelist()
def charge_credit_card(data, cardNumber, expirationDate, cardCode):
	"""
	Charge a credit card
	"""
	data = json.loads(data)
	data = frappe._dict(data)
	# Create a merchantAuthenticationType object with authentication details
	# retrieved from the constants file
	merchantAuth = apicontractsv1.merchantAuthenticationType()
	merchantAuth.name = frappe.db.get_value("Authorizenet Settings", "Authorizenet Settings", ["api_login_id"])
	merchantAuth.transactionKey = get_decrypted_password('Authorizenet Settings', 'Authorizenet Settings',fieldname='api_transaction_key', raise_exception=False)
	
	# Create the payment data for a credit card
	creditCard = apicontractsv1.creditCardType()
	creditCard.cardNumber = cardNumber
	creditCard.expirationDate = expirationDate
	creditCard.cardCode = cardCode

	# Add the payment data to a paymentType object
	payment = apicontractsv1.paymentType()
	payment.creditCard = creditCard

	# Update it in future with sales invoice
	# Create order information 
	# order = apicontractsv1.orderType()
	# order.invoiceNumber = "10101"
	# order.description = "Golf Shirts"

	# Create a transactionRequestType object and add the previous objects to it.
	transactionrequest = apicontractsv1.transactionRequestType()
	transactionrequest.transactionType = "authCaptureTransaction"
	transactionrequest.amount = data.amount
	transactionrequest.payment = payment

	# Assemble the complete transaction request
	createtransactionrequest = apicontractsv1.createTransactionRequest()
	createtransactionrequest.merchantAuthentication = merchantAuth
	createtransactionrequest.refId = "MerchantID-0001"
	createtransactionrequest.transactionRequest = transactionrequest
	# Create the controller
	createtransactioncontroller = createTransactionController(
		createtransactionrequest)
	createtransactioncontroller.execute()

	response = createtransactioncontroller.getresponse()

	if response is not None:
		# Check to see if the API request was successfully received and acted upon
		if response.messages.resultCode == "Ok":
			# Since the API request was successful, look for a transaction response
			# and parse it to display the results of authorizing the card
			if hasattr(response.transactionResponse, 'messages') is True:
				status = "Completed"
				print(
					'Successfully created transaction with Transaction ID: %s'
					% response.transactionResponse.transId)
				print('Transaction Response Code: %s' %
					  response.transactionResponse.responseCode)
				print('Message Code: %s' %
					  response.transactionResponse.messages.message[0].code)
				print('Description: %s' % response.transactionResponse.
					  messages.message[0].description)
			else:
				status = "Failed"
				print('Failed Transaction.')
				if hasattr(response.transactionResponse, 'errors') is True:
					print('Error Code:  %s' % str(response.transactionResponse.
												  errors.error[0].errorCode))
					print(
						'Error message: %s' %
						response.transactionResponse.errors.error[0].errorText)
					
		# Or, print errors if the API request wasn't successful
		else:
			status = "Failed"
			print('Failed Transaction.')
			if hasattr(response, 'transactionResponse') is True and hasattr(
					response.transactionResponse, 'errors') is True:
				print('Error Code: %s' % str(
					response.transactionResponse.errors.error[0].errorCode))
				print('Error message: %s' %
					  response.transactionResponse.errors.error[0].errorText)
				
			else:
				status = "Failed"
				print('Error Code: %s' %
					  response.messages.message[0]['code'].text)
				print('Error message: %s' %
					  response.messages.message[0]['text'].text)
				
	else:
		print('Null Response.')
	custom_redirect_to = None
	if status != "Failed":
		try:
			custom_redirect_to = frappe.get_doc(data.reference_doctype, data.reference_docname).run_method("on_payment_authorized",
				status)
		except Exception as ex:
			raise ex
	return status
