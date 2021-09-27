# Copyright (c) 2021, Frappe Technologies and Contributors
# See license.txt

import frappe
import unittest


class TestmPaySettings(unittest.TestCase):
	def setUp(self):
		self.mpay = frappe.get_doc({
			'doctype': 'mPay Settings',
			'merchantid': '1234567',
			'merchant_tid': '999',
			'securekey': 'ABCDEFG00GFEDCBA',
			'use_sandbox': 1,
			'redirect_url': 'https://redirect-url.com',
		})

	def tearDown(self):
		self.mpay.delete()

	def test_construct_text_params(self):
		with self.subTest('Text params from mpay Manual'):
			self.mpay.construct_text_params(
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
			self.assertEqual(
				self.mpay.text_params,
				'whi1i7lifa70yhgs;V30.0HKD1257984115649643163420180701010100zh_TW0011100000https://demo.mpay.com.hk/mpay/notify.jspHK2018070101010037https://demo.mpay.com.hk/return.jsp001101;ABCDEFG123456789',
			)

	def test_gen_text_hash(self):
		with self.subTest('Text params from mpay Manual'):
			self.mpay.text_params = 'whi1i7lifa70yhgs;V30.0HKD1257984115649643163420180701010100zh_TW0011100000https://demo.mpay.com.hk/mpay/notify.jspHK2018070101010037https://demo.mpay.com.hk/return.jsp001101;ABCDEFG123456789'
			self.mpay.gen_text_hash()
			self.assertEqual(
				self.mpay.text_hash.upper(),
				'0D959AA4CCBF2844B1DB7A3777772203712F31E04BAD9E208CB52BCA11FAF72B'
			)
