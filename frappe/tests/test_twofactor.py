# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import unittest, frappe
from werkzeug.wrappers import Request
from werkzeug.test import EnvironBuilder
from frappe.auth import LoginManager, HTTPRequest
from frappe.website import render


class TestTwoFactor(unittest.TestCase):


	def setUp(self):
		self.http_requests = create_http_request()
		self.login_manager = frappe.local.login_manager
		self.user = self.login_manager.user
		print self.user

	def test_debug(self):
		pass

	# def test_two_factor_auth_user(self):
	# 	'''Test OTP secret and verification method is initiated.'''
	# 	two_factor_role = self.login_manager.two_factor_auth_user()
	# 	otp_secret = frappe.db.get_default('test@erpnext.com_otpsecret')
	# 	self.assertFalse(two_factor_role)
	# 	toggle_2fa_all_role(True)
	# 	two_factor_role = self.login_manager.two_factor_auth_user()
	# 	self.assertTrue(two_factor_role)
	# 	self.assertNotEqual(otp_secret,None)
	# 	self.assertEqual(self.login_manager.verification_method,'OTP App')
	# 	frappe.db.set_default('test@erpnext.com_otpsecret', None)
	# 	toggle_2fa_all_role(False)

	# def test_get_verification_obj(self):
	# 	'''Auth url should be present in verification object.'''
	# 	verification_obj = self.login_manager.get_verification_obj()
	# 	self.assertIn('otpauth://',verification_obj['totp_uri'])
	# 	self.assertTrue(len(verification_obj['qrcode']) > 1 )

	# def test_process_2fa(self):
	# 	self.login_manager.process_2fa()
	# 	toggle_2fa_all_role(True)
	# 	print self.login_manager.info
	# 	# print frappe.local.response['verification']
	# 	# self.assertTrue(False not in [i in frappe.local.response['verification'] \
	# 	# 		for i in ['totp_uri','method','qrcode','setup']])
	# 	toggle_2fa_all_role(False)

	# def test_confirm_token(self):
	# 	pass

	# def test_send_token_via_sms(self):
	# 	pass

	# def test_send_token_via_email(self):
	# 	pass



def set_request(**kwargs):
	builder = EnvironBuilder(**kwargs)
	frappe.local.request = Request(builder.get_environ())

def create_http_request():
	'''Get http request object.'''
	set_request(method='POST', path='login')
	enable_2fa()
	frappe.form_dict['usr'] = 'test@erpnext.com'
	frappe.form_dict['pwd'] = 'test'
	frappe.local.form_dict['cmd'] = 'login'
	http_requests = HTTPRequest()
	return http_requests

def enable_2fa():
	'''Enable Two factor in system settings.'''
	system_settings = frappe.get_doc('System Settings')
	system_settings.enable_two_factor_auth = True
	system_settings.two_factor_method = 'OTP App'
	system_settings.save(ignore_permissions=True)
	frappe.db.commit()

def toggle_2fa_all_role(state=None):
	all_role = frappe.get_doc('Role','All')
	if state == None:
		state = False if all_role.two_factor_auth == True else False
	if state not in [True,False]:return
	all_role.two_factor_auth = state
	all_role.save(ignore_permissions=True)
	frappe.db.commit()
