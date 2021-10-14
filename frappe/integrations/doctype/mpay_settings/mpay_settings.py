# Copyright (c) 2021, Frappe Technologies and contributors
# For license information, please see license.txt

"""
# Integration for mPay
https://www.mpay.com.hk/
"""

import frappe
import json
import hashlib

from six.moves.urllib.parse import urlencode
from frappe import _
from frappe.model.document import Document
from frappe.integrations.utils import create_payment_gateway
from frappe.utils import get_url, call_hook_method, flt
from frappe.integrations.utils import create_request_log
from frappe.utils.password import get_decrypted_password


class PaymentGateway(Document):
	gateway_name = 'mPay'
	supported_currencies = []
	currency_wise_minimum_charge_amount = {}
	sandbox_url = ''
	prod_url = ''

	def vaildate(self):
		if not self.flags.ignore_mandatory:
			self.validate_credentials()

	def on_update(self):
		create_payment_gateway(
			gateway=self.gateway_name,
		)
		call_hook_method(
			'payment_gateway_enabled',
			gateway=self.gateway_name
		)

	def validate_credentials():
		pass

	def validate_transaction_currency(self, currency):
		if currency not in self.supported_currencies:
			frappe.throw(_(
				"Please select another payment method. {gateway} does not support transactions in currency '{currency}'"
			).format(
				gateway=self.gateway_name,
				currency=currency
			))

	def validate_minimum_transaction_amount(self, currency, amount):
		if currency in self.currency_wise_minimum_charge_amount:
			if flt(amount) < self.currency_wise_minimum_charge_amount.get(currency, 0.0):
				frappe.throw(_('For currency {0}, the minimum transaction amount should be {1}').format(
					currency,
					self.currency_wise_minimum_charge_amount.get(currency, 0.0)
				))

	def create_payment_request(self, data):
		try:
			self.integration_request = create_request_log(
				data, 'Host', self.gateway_name,
			)

		except Exception:
			frappe.log_error(frappe.get_traceback())
			return{
				'redirect_to': frappe.redirect_to_message(
					_('Server Error'),
					_((
						"There seems to be an issue with the server's {gateway} configuration."
						"Don't worry, in case of failure, the amount will get refunded to your account."
					).format(gateway=self.gateway_name))),
				'status': 401
			}


class mPaySettings(PaymentGateway):
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

	def get_payment_url(self, **kwargs):
		self.create_payment_request(data=frappe._dict(kwargs))
		return get_url('./integrations/mpay_checkout?{0}'.format(
			urlencode({
				'order_id': self.integration_request.name,
			})
		))

	def get_gateway_settings(self):
		self.gateway_settings = {
			'merchantid': self.merchantid,
			'merchant_tid': self.merchant_tid,
			'returnurl': self.redirect_url,
			'securekey': get_decrypted_password(
				doctype='mPay Settings',
				name='mPay Settings',
				fieldname='securekey'
			),
		}

	def construct_text_params(self, **kwargs):
		"""Combine all params, return as string"""
		self.get_gateway_settings()
		dict_params = {
			**self.gateway_settings,
			**{
				# salt value generated, used for security validation
				# random alphanumeric values with length 16 (e.g. whi1i7lifa70yhgs)
				'salt': frappe.generate_hash(length=16),
				# choose payment method at mPay side
				'paymethod': 0,
				# datetime in "yyyyMMddHHmmss" format
				'datetime': frappe.utils.data.now_datetime().strftime('%Y%m%d%H%M%S'),
				# store ID of this transaction take place
				# if not used, just put in "1" as default
				'storeid': 1,
				# the notify URL of merchant which receive payment response from mPay server
				'notifyurl': 'https://dummy.com',
				# language used in mPay side
				'locale': 'en_US',
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
			if key in dict_params:
				val = dict_params.get(key, None)
				if val is not None:
					params_list.append(str(val))

		params_text = ''.join(params_list)

		text_params = '{salt};{params_text};{securekey}'.format(
			salt=dict_params.get('salt'),
			params_text=params_text,
			securekey=dict_params.get('securekey'),
		)

		self.text_params = text_params
		self.dict_params = dict_params

	def gen_text_hash(self):
		m = hashlib.sha256()
		m.update(self.text_params.encode('utf-8'))
		self.text_hash = hashlib.sha256(
			self.text_params.encode('utf-8')
		).hexdigest()

	@staticmethod
	def map_payment_key(params_dict):
		map_dict = {
			# 'frappe_key': 'mpay_key',
			'amount': 'amt',
			'currency': 'currency',
			'reference_docname': 'ordernum',
			'payer_name': 'customerid',
		}

		for frappe_key, mpay_key in map_dict.items():
			if frappe_key in params_dict:
				params_dict[mpay_key] = params_dict.pop(frappe_key)

		return params_dict

	def get_payment_context(self, integration_request_id):
		integration_request = frappe.get_doc(
			'Integration Request',
			integration_request_id
		).as_dict()

		integration_request_data = json.loads(integration_request.data)
		request_data = self.map_payment_key(integration_request_data)

		self.construct_text_params(**request_data)
		self.gen_text_hash()

		self.dict_params.pop('securekey')
		self.dict_params['version'] = self.api_version
		self.dict_params['hash'] = self.text_hash

		if self.use_sandbox:
			url = self.sandbox_url
		else:
			url = self.prod_url

		context = {
			'url': url,
			'data': self.dict_params,
		}

		return context
