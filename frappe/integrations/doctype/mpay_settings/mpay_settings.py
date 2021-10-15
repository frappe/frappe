# Copyright (c) 2021, Frappe Technologies and contributors
# For license information, please see license.txt

"""
# Integration for mPay
https://www.mpay.com.hk
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

	request_params_list = [
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
	response_params_list = [
		"accounttype",
		"amt",
		"authcode",
		"cardnum",
		"currency",
		"customerid",
		"customizeddata",
		"fi_post_dt",
		"merchant_tid",
		"merchantid",
		"ordernum",
		"paymethod",
		"ref",
		"rspcode",
		"settledate",
		"storeid",
		"sysdatetime",
		"tokenid",
	]

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
			'securekey': get_decrypted_password(
				doctype='mPay Settings',
				name='mPay Settings',
				fieldname='securekey'
			),
		}

	def construct_request_params(self, **kwargs):
		"""Combine all params, return request data with hash and other value"""
		self.get_gateway_settings()
		request_dict_params = {
			**self.gateway_settings,
			**{
				'ordernum': self.integration_request_name,
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
				# return URL which payment response pass back by
				# customer’s browser redirection
				'returnurl': get_url('/api/method/frappe.integrations.doctype.mpay_settings.mpay_settings.return_url'),
				# the notify URL of merchant which receive payment response from mPay server
				'notifyurl': get_url('/api/method/frappe.integrations.doctype.mpay_settings.mpay_settings.notify_url'),
				# language used in mPay side
				'locale': 'en_US',
			},
			**kwargs,
		}

		request_text_params = self.params_dict_to_text(
			params_dict=request_dict_params,
			params_key_list=self.request_params_list,
		)
		request_text_params = '{salt};{params_text};{securekey}'.format(
			salt=request_dict_params.get('salt'),
			params_text=request_text_params,
			securekey=request_dict_params.get('securekey'),
		)
		request_text_hash = self.gen_text_hash(
			request_text_params
		)

		request_dict_params = self.select_params(
			params_dict=request_dict_params,
			params_key_list=self.request_params_list,
		)
		request_dict_params['version'] = self.api_version
		request_dict_params['hash'] = request_text_hash

		return request_dict_params

	@staticmethod
	def select_params(params_dict, params_key_list):
		_params_key_list = params_key_list.copy()
		_params_key_list.append('salt')
		selected_params_dict = {}
		for key in _params_key_list:
			if key in params_dict:
				val = params_dict.get(key, None)
				if val is not None:
					selected_params_dict[key] = params_dict[key]

		return selected_params_dict

	@staticmethod
	def params_dict_to_text(params_dict, params_key_list):
		params_list = []
		for key in params_key_list:
			if key in params_dict:
				val = params_dict.get(key, None)
				if val is not None:
					params_list.append(str(val))

		params_text = ''.join(params_list)

		return params_text

	@staticmethod
	def gen_text_hash(params_text):
		m = hashlib.sha256()
		m.update(params_text.encode('utf-8'))
		text_hash = hashlib.sha256(
			params_text.encode('utf-8')
		).hexdigest()
		return text_hash

	@staticmethod
	def map_payment_key(params_dict):
		map_dict = {
			# 'frappe_key': 'mpay_key',
			'amount': 'amt',
			'currency': 'currency',
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
		self.integration_request_name = integration_request_id

		integration_request_data = json.loads(integration_request.data)
		request_data = self.map_payment_key(integration_request_data)

		request_data = self.construct_request_params(**request_data)

		if self.use_sandbox:
			url = self.sandbox_url
		else:
			url = self.prod_url

		context = {
			'url': url,
			'data': request_data,
		}

		return context

	def update_integration_request(self):
		response_data = self.response_data
		request_id = response_data.get('ordernum')
		response_code = response_data.get('rspcode')
		request_doc = frappe.get_doc('Integration Request', request_id)

		if response_code == '100':
			request_doc.db_set('status', 'Completed')
		else:
			request_doc.db_set('status', 'Failed')

		# pop private info from kwargs
		response_data.pop('hash')
		response_data.pop('salt')

		# append response to request data
		request_data = json.loads(request_doc.data)
		request_data['response_data'] = response_data
		request_data_str = json.dumps(request_data)

		request_doc.db_set('data', request_data_str)

		self.response_code = response_code
		self.ref_doctype = request_data.get('reference_doctype')
		self.ref_docname = request_data.get('reference_docname')

		return response_code

	def run_payment_authorized(self):
		redirect_to = None
		if self.ref_doctype and self.ref_docname and self.response_code == '100':
			try:
				ref_doc = frappe.get_doc(self.ref_doctype, self.ref_docname)
				redirect_to = ref_doc.run_method(
					'on_payment_authorized', 'Completed'
				)
			except Exception:
				frappe.log_error(frappe.get_traceback())

		return redirect_to

	def verify_return_data(self):
		return_text_params = self.params_dict_to_text(
			params_dict=self.response_data,
			params_key_list=self.response_params_list,
		)
		return_text_params = '{securekey};{params_text};{salt}'.format(
			salt=self.response_data.get('salt'),
			params_text=return_text_params,
			securekey=get_decrypted_password(
				doctype='mPay Settings',
				name='mPay Settings',
				fieldname='securekey'
			),
		)
		return_text_hash = self.gen_text_hash(
			return_text_params
		)

		if return_text_hash.upper() != self.response_data.get('hash').upper():
			frappe.log_error(
				title=_('Invalid mPay return data'),
				message=self.response_data,
			)
			frappe.throw(_('Invalid mPay return data'))

	def handle_return(self, response_data):
		self.response_data = response_data
		self.verify_return_data()
		response_code = self.update_integration_request()
		redirect_to = self.run_payment_authorized()
		return {
			'response_code': response_code,
			'redirect_to': redirect_to,
		}


"""
# [FROM mPay MANUAL]
# Merchant Client Response Message (mPay to Merchant)

The following parameters are returned from mPay to merchant for BOTH return URL(successful and fail transaction)
and notify URL (successful transaction only by default).

For Return URL, the response parameters are returned as Name Value Pair with POST method by default.
Merchant can request to change to GET method.

For Notify URL, the response parameters are returned as Name Value Pair by default. Merchant can request
to change to JSON format.
"""


@frappe.whitelist(allow_guest=True, xss_safe=True)
def notify_url(**response_kwargs):
	"""Notify url will be call **ONLY IF TRANSACTION IS SUCCESSFUL**

	This method is somewhat repetitive with return_url method,
	but it might be useful for somecase such as
	user close browser exactly when payment successful then return url don't get call
	and status didn't get update

	So for this method we'll check if Integration Request is still in pending
	if it is then update success status
	"""
	request_status = frappe.get_value(
		doctype='Integration Request',
		filters=response_kwargs.get('ordernum'),
		fieldname='status'
	)
	if (request_status != 'Queued'):
		return

	mPay = frappe.get_doc('mPay Settings')
	mPay.handle_return(response_kwargs)


@frappe.whitelist(allow_guest=True, xss_safe=True)
def return_url(**response_kwargs):
	"""Determine if payment is successful or not,
	update Integration Request then redirect to
	payment success or failed accordingly
	"""
	mPay = frappe.get_doc('mPay Settings')
	m = mPay.handle_return(response_kwargs)
	response_code = m.get('response_code')
	redirect_to = m.get('redirect_to')

	redirect_msg = None
	if response_code == '100':
		redirect_url = '/integrations/payment-success'
	else:
		redirect_url = '/integrations/payment-failed'
		redirect_msg = 'mPay Error Code: {}'.format(response_code)

	if redirect_to:
		redirect_url += '?' + urlencode({'redirect_to': redirect_to})
	if redirect_msg:
		redirect_url += '&' + urlencode({'redirect_message': redirect_msg})

	frappe.local.response['type'] = 'redirect'
	frappe.local.response['location'] = redirect_url
