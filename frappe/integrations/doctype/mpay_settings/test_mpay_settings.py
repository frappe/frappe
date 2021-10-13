# Copyright (c) 2021, Frappe Technologies and Contributors
# See license.txt

import frappe
import json
import unittest


class TestmPaySettings(unittest.TestCase):
	def setUp(self):
		self.mpay_settings = {
			'merchantid': '1234567',
			'merchant_tid': '999',
			'securekey': 'ABCDEFG00GFEDCBA',
			'use_sandbox': 1,
			'redirect_url': 'https://redirect-url.com',
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
			'title': frappe.generate_hash(),
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
				'returnurl': 'https://redirect-url.com',
				'securekey': 'ABCDEFG00GFEDCBA',
			},
		)

	def test_construct_text_params(self):
		with self.subTest('Text params from mpay Manual'):
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
			self.mpay.construct_text_params(**params)
			self.assertEqual(
				self.mpay.text_params,
				'whi1i7lifa70yhgs;V30.0HKD1257984115649643163420180701010100zh_TW0011100000https://demo.mpay.com.hk/mpay/notify.jspHK2018070101010037https://demo.mpay.com.hk/return.jsp001101;ABCDEFG123456789',
			)

			self.assertEqual(
				self.mpay.dict_params,
				params,
			)

	def test_gen_text_hash(self):
		with self.subTest('Text params from mpay Manual'):
			self.mpay.text_params = 'whi1i7lifa70yhgs;V30.0HKD1257984115649643163420180701010100zh_TW0011100000https://demo.mpay.com.hk/mpay/notify.jspHK2018070101010037https://demo.mpay.com.hk/return.jsp001101;ABCDEFG123456789'
			self.mpay.gen_text_hash()
			self.assertEqual(
				self.mpay.text_hash.upper(),
				'0D959AA4CCBF2844B1DB7A3777772203712F31E04BAD9E208CB52BCA11FAF72B'
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
				"ordernum": "04fb9bd3",
				"payer_email": "someone@mpaytest.com",
				"customerid": "someonetest",
				"order_id": "orderid0124",
				"currency": "HKD"
			},
		)

	def test_get_payment_context(self):
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
