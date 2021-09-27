# Copyright (c) 2021, Frappe Technologies and contributors
# For license information, please see license.txt

"""
# Integration for mPay
https://www.mpay.com.hk/
"""

import frappe
import base64
import hmac
import hashlib
from frappe import _
from frappe.model.document import Document
from frappe.integrations.utils import create_payment_gateway
from frappe.utils import get_url, call_hook_method, cint, flt
from six.moves.urllib.parse import urlencode


class mPaySettings(Document):
	supported_currencies = [
		'HKD', 'RMB', 'USD'
	]

	currency_wise_minimum_charge_amount = {
		'HKD': 10,
		'RMB': 10,
		'USD': 2,
	}

	api_version = '5.0'

	sandbox_url = 'https://demo.mobiletech.com.hk/MPay/MerchantPay.jsp'
	prod_url = 'https://mobiletech.com.hk/MPay/MerchantPay.jsp'

	def validate(self):
		if not self.flags.ignore_mandatory:
			self.validate_mpay_credentails()

	def on_update(self):
		create_payment_gateway(
			gateway='mPay',
		)
		call_hook_method('payment_gateway_enabled', gateway='mPay')

	def validate_mpay_credentails(self):
		pass

	def validate_transaction_currency(self, currency):
		if currency not in self.supported_currencies:
			frappe.throw(_(
				"Please select another payment method. mPay does not support transactions in currency '{0}'"
			).format(currency))

	def validate_minimum_transaction_amount(self, currency, amount):
		if currency in self.currency_wise_minimum_charge_amount:
			if flt(amount) < self.currency_wise_minimum_charge_amount.get(currency, 0.0):
				frappe.throw(_('For currency {0}, the minimum transaction amount should be {1}').format(
					currency,
					self.currency_wise_minimum_charge_amount.get(currency, 0.0)
				))

	def get_payment_url(self, **kwargs):
		pass

	def construct_text_params(self, **kwargs):
		"""Combine all params, return as string"""
		params_dict = {
			**{
				'merchantid': self.merchantid,
				'merchant_tid': self.merchant_tid,
				'returnurl': self.redirect_url,
				'securekey': self.securekey,
				'salt': frappe.generate_hash(length=16),
			},
			**kwargs,
		}

		params_key_list = [
			'accounttype',
			'amt',
			'currency',
			'customerid',
			'customizeddata',
			'datetime',
			'extrafield1',
			'extrafield2',
			'extrafield3',
			'locale',
			'merchant_tid',
			'merchantid',
			'notifyurl',
			'ordernum',
			'paymethod',
			'returnurl',
			'storeid',
			'tokenid',
		]

		params_list = []
		for key in params_key_list:
			if key in params_dict:
				params_list.append(kwargs.get(key))

		params_text = ''.join(params_list)

		text_params = '{salt};{params_text};{securekey}'.format(
			salt=params_dict.get('salt'),
			params_text=params_text,
			securekey=params_dict.get('securekey'),
		)

		self.text_params = text_params

	def gen_text_hash(self):
		m = hashlib.sha256()
		m.update(self.text_params.encode('utf-8'))
		self.text_hash = hashlib.sha256(
			self.text_params.encode('utf-8')
		).hexdigest()
