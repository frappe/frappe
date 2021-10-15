# Copyright (c) 2021, Frappe Technologies and Contributors
# See license.txt

import frappe
import json
import unittest

from frappe.exceptions import ValidationError


class TestmPaySettings(unittest.TestCase):
	def setUp(self):
		self.mpay_settings = {
			'merchantid': '1234567',
			'merchant_tid': '999',
			'securekey': 'ABCDEFG00GFEDCBA',
			'use_sandbox': 1,
		}
		self.mpay = frappe.get_doc(
			**{
				'doctype': 'mPay Settings',
			},
			**self.mpay_settings
		)
		self.mpay.insert()

		self.ref_doc = frappe.get_doc({
			'doctype': 'Note',
			'title': frappe.generate_hash(length=5),
			'content': """
				Use note as reference doc for Payment Request doctype,
				since note doesn't have any other doctype dependencies
				such as company or customer, so we don't have to set those up
			"""
		})
		self.ref_doc.insert()

	def tearDown(self):
		self.mpay.delete()
		frappe.db.rollback()

	def test_get_payment_url(self):
		self.assertRegex(
			self.mpay.get_payment_url(**{
				'amount': 100,
				'title': 'mPay testing',
				'description': 'mPay unittest',
				'reference_doctype': self.ref_doc.doctype,
				'reference_docname': self.ref_doc.name,
				'payer_email': 'someone@mpaytest.com',
				'payer_name': 'someonetest',
				'order_id': 'orderid0124',
				'currency': 'HKD'
			}),
			r'^http.*\/integrations\/mpay_checkout\?order_id=[\w\d]*$'
		)

	def test_create_payment_request(self):
		data = dict(
			salt="whi1i7lifa70yhgs",
			securekey="ABCDEFG123456789",
			accounttype="V",
			amt="30.0",
			currency="HKD",
			customerid="12579841156496431634",
			datetime="20180701010100",
			locale="zh_TW",
			merchant_tid="001",
			merchantid="1100000",
			notifyurl="https://demo.mpay.com.hk/mpay/notify.jsp",
			ordernum="HK20180701010100",
			paymethod="37",
			returnurl="https://demo.mpay.com.hk/return.jsp",
			storeid="001",
			tokenid="101",
		)
		self.mpay.create_payment_request(
			data=data
		)

		self.assertTrue(
			hasattr(self.mpay.integration_request, 'name')
		)
		self.assertEqual(
			data,
			json.loads(self.mpay.integration_request.data),
		)

	def test_get_gateway_settings(self):
		self.mpay.get_gateway_settings()
		self.assertEqual(
			self.mpay.gateway_settings,
			{
				'merchant_tid': '999',
				'merchantid': '1234567',
				'securekey': 'ABCDEFG00GFEDCBA',
			},
		)

	def test_construct_request_params(self):
		with self.subTest('Text params from mpay Manual'):
			self.mpay.integration_request_name = 'asd7lifa7'
			params = dict(
				salt="whi1i7lifa70yhgs",
				securekey="ABCDEFG123456789",
				accounttype="V",
				amt="30.0",
				currency="HKD",
				customerid="12579841156496431634",
				datetime="20180701010100",
				locale="zh_TW",
				merchant_tid="001",
				merchantid="1100000",
				notifyurl="https://demo.mpay.com.hk/mpay/notify.jsp",
				ordernum="HK20180701010100",
				paymethod="37",
				returnurl="https://demo.mpay.com.hk/return.jsp",
				storeid="001",
				tokenid="101",
			)
			request_dict_params = self.mpay.construct_request_params(**params)
			self.assertEqual(
				request_dict_params,
				{
					"merchantid": "1100000",
					"merchant_tid": "001",
					"returnurl": "https://demo.mpay.com.hk/return.jsp",
					"salt": "whi1i7lifa70yhgs",
					"paymethod": "37",
					"datetime": "20180701010100",
					"storeid": "001",
					"notifyurl": "https://demo.mpay.com.hk/mpay/notify.jsp",
					"locale": "zh_TW",
					"accounttype": "V",
					"amt": "30.0",
					"currency": "HKD",
					"customerid": "12579841156496431634",
					"ordernum": "HK20180701010100",
					"tokenid": "101",
					"version": "5.0",
					"hash": "0d959aa4ccbf2844b1db7a3777772203712f31e04bad9e208cb52bca11faf72b"
				},
			)

	def test_select_params(self):
		params = dict(
			salt="whi1i7lifa70yhgs",
			accounttype="V",
			amt="30.0",
			currency="HKD",
			customerid="12579841156496431634",
			datetime="20180701010100",
			locale="zh_TW",
			merchant_tid="001",
			merchantid="1100000",
			notifyurl="https://demo.mpay.com.hk/mpay/notify.jsp",
			ordernum="HK20180701010100",
			paymethod="37",
			returnurl="https://demo.mpay.com.hk/return.jsp",
			storeid="001",
			tokenid="101",
			reference_doctype="Some Doctype",
			reference_docname="Some Docname",
		)

		self.assertDictEqual(
			self.mpay.select_params(
				params_dict=params,
				params_key_list=self.mpay.request_params_list,
			),
			dict(
				salt="whi1i7lifa70yhgs",
				accounttype="V",
				amt="30.0",
				currency="HKD",
				customerid="12579841156496431634",
				datetime="20180701010100",
				locale="zh_TW",
				merchant_tid="001",
				merchantid="1100000",
				notifyurl="https://demo.mpay.com.hk/mpay/notify.jsp",
				ordernum="HK20180701010100",
				paymethod="37",
				returnurl="https://demo.mpay.com.hk/return.jsp",
				storeid="001",
				tokenid="101",
			)
		)

	def test_params_dict_to_text(self):
		with self.subTest('request_data'):
			params_dict = dict(
				salt="whi1i7lifa70yhgs",
				accounttype="V",
				amt="30.0",
				currency="HKD",
				customerid="12579841156496431634",
				datetime="20180701010100",
				locale="zh_TW",
				merchant_tid="001",
				merchantid="1100000",
				notifyurl="https://demo.mpay.com.hk/mpay/notify.jsp",
				ordernum="HK20180701010100",
				paymethod="37",
				returnurl="https://demo.mpay.com.hk/return.jsp",
				storeid="001",
				tokenid="101",
			)
			params_text = self.mpay.params_dict_to_text(
				params_dict=params_dict,
				params_key_list=self.mpay.request_params_list,
			)
			self.assertEqual(
				params_text,
				'V30.0HKD1257984115649643163420180701010100zh_TW0011100000https://demo.mpay.com.hk/mpay/notify.jspHK2018070101010037https://demo.mpay.com.hk/return.jsp001101',
			)

		with self.subTest('with return data'):
			return_data = dict(
				version="5.0",
				salt="whi1i7lifa70yhgs",
				accounttype="V",
				amt="30.0",
				authcode="",
				cardnum="456789xxxxxx6789",
				currency="HKD",
				customerid="12579841156496431634",
				customizeddata="",
				fi_post_dt="20180701010100",
				merchant_tid="001",
				merchantid="1100000",
				ordernum="HK20180701010100",
				paymethod="37",
				ref="370000111111",
				rspcode="100",
				settledate="20180701010100",
				storeid="001",
				sysdatetime="20180701010100",
				tokenid="101",
				hash="D4ED49F985972DAE258439DC57ADA1C20BD3D797C1510DEC54ACF2CC8B9B4988",
			)
			params_text = self.mpay.params_dict_to_text(
				params_dict=return_data,
				params_key_list=self.mpay.response_params_list,
			)
			self.assertEqual(
				params_text,
				'V30.0456789xxxxxx6789HKD12579841156496431634201807010101000011100000HK20180701010100373700001111111002018070101010000120180701010100101',
			)

	def test_gen_text_hash(self):
		with self.subTest('Text params from mpay Manual, request data'):
			text_params = 'whi1i7lifa70yhgs;V30.0HKD1257984115649643163420180701010100zh_TW0011100000https://demo.mpay.com.hk/mpay/notify.jspHK2018070101010037https://demo.mpay.com.hk/return.jsp001101;ABCDEFG123456789'
			text_hash = self.mpay.gen_text_hash(text_params)
			self.assertEqual(
				text_hash.upper(),
				'0D959AA4CCBF2844B1DB7A3777772203712F31E04BAD9E208CB52BCA11FAF72B'
			)

		with self.subTest('Text params from mpay Manual, response data'):
			text_params = 'ABCDEFG123456789;V30.0456789xxxxxx6789HKD12579841156496431634201807010101000011100000HK20180701010100373700001111111002018070101010000120180701010100101;whi1i7lifa70yhgs'
			text_hash = self.mpay.gen_text_hash(text_params)
			self.assertEqual(
				text_hash.upper(),
				'D4ED49F985972DAE258439DC57ADA1C20BD3D797C1510DEC54ACF2CC8B9B4988'
			)

	def test_map_payment_key(self):
		self.assertDictEqual(
			self.mpay.map_payment_key({
				"amount": 100,
				"title": "mPay testing",
				"description": "mPay unittest",
				"reference_doctype": "Note",
				"reference_docname": "04fb9bd3",
				"payer_email": "someone@mpaytest.com",
				"payer_name": "someonetest",
				"order_id": "orderid0124",
				"currency": "HKD"
			}),
			{
				"amt": 100,
				"title": "mPay testing",
				"description": "mPay unittest",
				"reference_doctype": "Note",
				"reference_docname": "04fb9bd3",
				"order_id": "orderid0124",
				"payer_email": "someone@mpaytest.com",
				"customerid": "someonetest",
				"currency": "HKD"
			},
		)

	def test_get_payment_context(self):
		self.maxDiff = None
		data = dict(
			salt="whi1i7lifa70yhgs",
			securekey="ABCDEFG123456789",
			accounttype="V",
			amt="30.0",
			currency="HKD",
			customerid="12579841156496431634",
			datetime="20180701010100",
			locale="zh_TW",
			merchant_tid="001",
			merchantid="1100000",
			notifyurl="https://demo.mpay.com.hk/mpay/notify.jsp",
			ordernum="HK20180701010100",
			paymethod="37",
			returnurl="https://demo.mpay.com.hk/return.jsp",
			storeid="001",
			tokenid="101",
		)
		self.mpay.create_payment_request(data=data)
		payment_context = self.mpay.get_payment_context(
			integration_request_id=self.mpay.integration_request.name,
		)

		self.assertEqual(
			payment_context,
			{
				'url': 'https://demo.mobiletech.com.hk/MPay/MerchantPay.jsp',
				'data': dict(
					version="5.0",
					salt="whi1i7lifa70yhgs",
					accounttype="V",
					amt="30.0",
					currency="HKD",
					customerid="12579841156496431634",
					datetime="20180701010100",
					locale="zh_TW",
					merchant_tid="001",
					merchantid="1100000",
					notifyurl="https://demo.mpay.com.hk/mpay/notify.jsp",
					ordernum="HK20180701010100",
					paymethod="37",
					returnurl="https://demo.mpay.com.hk/return.jsp",
					storeid="001",
					tokenid="101",
					hash="0d959aa4ccbf2844b1db7a3777772203712f31e04bad9e208cb52bca11faf72b"
				)
			}
		)

	def test_verify_return_data(self):
		with self.subTest('validation, pass'):
			self.mpay.securekey = "ABCDEFG123456789"
			self.mpay.save()

			return_data = dict(
				version="5.0",
				salt="whi1i7lifa70yhgs",
				accounttype="V",
				amt="30.0",
				authcode="",
				cardnum="456789xxxxxx6789",
				currency="HKD",
				customerid="12579841156496431634",
				customizeddata="",
				fi_post_dt="20180701010100",
				merchant_tid="001",
				merchantid="1100000",
				ordernum="HK20180701010100",
				paymethod="37",
				ref="370000111111",
				rspcode="100",
				settledate="20180701010100",
				storeid="001",
				sysdatetime="20180701010100",
				tokenid="101",
				hash="D4ED49F985972DAE258439DC57ADA1C20BD3D797C1510DEC54ACF2CC8B9B4988",
			)

			self.mpay.response_data = return_data
			self.mpay.verify_return_data()

		with self.subTest('validation throw error'):
			self.mpay.securekey = "ABCDEFG123456789"
			self.mpay.save()

			return_data = dict(
				version="5.0",
				salt="whi1i7lifa70yhgs",
				accounttype="V",
				amt="30.0",
				authcode="",
				cardnum="456789xxxxxx6789",
				currency="HKD",
				customerid="12579841156496431634",
				customizeddata="",
				fi_post_dt="20180701010100",
				merchant_tid="001",
				merchantid="1100000",
				ordernum="HK20180701010100",
				paymethod="37",
				ref="370000111111",
				rspcode="100",
				settledate="20180701010100",
				storeid="001",
				sysdatetime="20180701010100",
				tokenid="101",
				hash="INVALID_HASH_E258439DC57ADA1C20BD3D797C1510DEC54ACF2CC8B9B4988",
			)

			self.mpay.response_data = return_data
			self.assertRaises(
				ValidationError,
				self.mpay.verify_return_data,
			)

	def test_update_integration_request(self):
		pass

	def test_run_payment_authorized(self):
		pass
