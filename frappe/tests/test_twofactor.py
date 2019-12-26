# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import unittest, frappe, pyotp
from frappe.auth import HTTPRequest
from frappe.utils import cint
from frappe.tests import set_request
from frappe.auth import validate_ip_address
from frappe.twofactor import (should_run_2fa, authenticate_for_2factor, get_cached_user_pass,
	two_factor_is_enabled_for_, confirm_otp_token, get_otpsecret_for_, get_verification_obj)

import time

class TestTwoFactor(unittest.TestCase):
	def setUp(self):
		self.http_requests = create_http_request()
		self.login_manager = frappe.local.login_manager
		self.user = self.login_manager.user

	def tearDown(self):
		frappe.local.response['verification'] = None
		frappe.local.response['tmp_id'] = None
		disable_2fa()
		frappe.clear_cache(user=self.user)

	def test_should_run_2fa(self):
		'''Should return true if enabled.'''
		toggle_2fa_all_role(state=True)
		self.assertTrue(should_run_2fa(self.user))
		toggle_2fa_all_role(state=False)
		self.assertFalse(should_run_2fa(self.user))

	def test_get_cached_user_pass(self):
		'''Cached data should not contain user and pass before 2fa.'''
		user,pwd = get_cached_user_pass()
		self.assertTrue(all([not user, not pwd]))

	def test_authenticate_for_2factor(self):
		'''Verification obj and tmp_id should be set in frappe.local.'''
		authenticate_for_2factor(self.user)
		verification_obj = frappe.local.response['verification']
		tmp_id = frappe.local.response['tmp_id']
		self.assertTrue(verification_obj)
		self.assertTrue(tmp_id)
		for k in ['_usr','_pwd','_otp_secret']:
			self.assertTrue(frappe.cache().get('{0}{1}'.format(tmp_id,k)),
							'{} not available'.format(k))

	def test_two_factor_is_enabled(self):
		'''
		1. Should return true, if enabled and not bypass_2fa_for_retricted_ip_users
		2. Should return false, if not enabled
		3. Should return true, if enabled and not bypass_2fa_for_retricted_ip_users and ip in restrict_ip
		4. Should return true, if enabled and bypass_2fa_for_retricted_ip_users and not restrict_ip
		5. Should return false, if enabled and bypass_2fa_for_retricted_ip_users and ip in restrict_ip
		'''

		#Scenario 1
		enable_2fa()
		self.assertTrue(should_run_2fa(self.user))

		#Scenario 2
		disable_2fa()
		self.assertFalse(should_run_2fa(self.user))

		#Scenario 3
		enable_2fa()
		user = frappe.get_doc('User', self.user)
		user.restrict_ip = frappe.local.request_ip
		user.save()
		self.assertTrue(should_run_2fa(self.user))

		#Scenario 4
		user = frappe.get_doc('User', self.user)
		user.restrict_ip = ""
		user.save()
		enable_2fa(1)
		self.assertTrue(should_run_2fa(self.user))

		#Scenario 5
		user = frappe.get_doc('User', self.user)
		user.restrict_ip = frappe.local.request_ip
		user.save()
		enable_2fa(1)
		self.assertFalse(should_run_2fa(self.user))

	def test_two_factor_is_enabled_for_user(self):
		'''Should return true if enabled for user.'''
		toggle_2fa_all_role(state=True)
		self.assertTrue(two_factor_is_enabled_for_(self.user))
		self.assertFalse(two_factor_is_enabled_for_("Administrator"))
		toggle_2fa_all_role(state=False)
		self.assertFalse(two_factor_is_enabled_for_(self.user))

	def test_get_otpsecret_for_user(self):
		'''OTP secret should be set for user.'''
		self.assertTrue(get_otpsecret_for_(self.user))
		self.assertTrue(frappe.db.get_default(self.user + '_otpsecret'))

	def test_confirm_otp_token(self):
		'''Ensure otp is confirmed'''
		authenticate_for_2factor(self.user)
		tmp_id = frappe.local.response['tmp_id']
		otp = 'wrongotp'
		with self.assertRaises(frappe.AuthenticationError):
			confirm_otp_token(self.login_manager,otp=otp,tmp_id=tmp_id)
		otp = get_otp(self.user)
		self.assertTrue(confirm_otp_token(self.login_manager,otp=otp,tmp_id=tmp_id))
		if frappe.flags.tests_verbose:
			print('Sleeping for 30secs to confirm token expires..')
		time.sleep(30)
		with self.assertRaises(frappe.AuthenticationError):
			confirm_otp_token(self.login_manager,otp=otp,tmp_id=tmp_id)

	def test_get_verification_obj(self):
		'''Confirm verification object is returned.'''
		otp_secret = get_otpsecret_for_(self.user)
		token = int(pyotp.TOTP(otp_secret).now())
		self.assertTrue(get_verification_obj(self.user,token,otp_secret))

	def test_render_string_template(self):
		'''String template renders as expected with variables.'''
		args = {'issuer_name':'Frappe Technologies'}
		_str = 'Verification Code from {{issuer_name}}'
		_str = frappe.render_template(_str,args)
		self.assertEqual(_str,'Verification Code from Frappe Technologies')

	def test_bypass_restict_ip(self):
		'''
		1. Raise error if user not login from one of the restrict_ip, Bypass restrict ip check disabled by default
		2. Bypass restrict ip check enabled in System Settings
		3. Bypass restrict ip check enabled for User
		'''

		#1
		user = frappe.get_doc('User', self.user)
		user.restrict_ip = "192.168.255.254" #Dummy IP
		user.bypass_restrict_ip_check_if_2fa_enabled = 0
		user.save()
		enable_2fa(bypass_restrict_ip_check=0)
		with self.assertRaises(frappe.AuthenticationError):
			validate_ip_address(self.user)

		#2
		enable_2fa(bypass_restrict_ip_check=1)
		self.assertIsNone(validate_ip_address(self.user))

		#3
		user = frappe.get_doc('User', self.user)
		user.bypass_restrict_ip_check_if_2fa_enabled = 1
		user.save()
		enable_2fa()
		self.assertIsNone(validate_ip_address(self.user))

def create_http_request():
	'''Get http request object.'''
	set_request(method='POST', path='login')
	enable_2fa()
	frappe.form_dict['usr'] = 'test@erpnext.com'
	frappe.form_dict['pwd'] = 'test'
	frappe.local.form_dict['cmd'] = 'login'
	http_requests = HTTPRequest()
	return http_requests

def enable_2fa(bypass_two_factor_auth=0, bypass_restrict_ip_check=0):
	'''Enable Two factor in system settings.'''
	system_settings = frappe.get_doc('System Settings')
	system_settings.enable_two_factor_auth = 1
	system_settings.bypass_2fa_for_retricted_ip_users = cint(bypass_two_factor_auth)
	system_settings.bypass_restrict_ip_check_if_2fa_enabled = cint(bypass_restrict_ip_check)
	system_settings.two_factor_method = 'OTP App'
	system_settings.save(ignore_permissions=True)
	frappe.db.commit()

def disable_2fa():
	system_settings = frappe.get_doc('System Settings')
	system_settings.enable_two_factor_auth = 0
	system_settings.save(ignore_permissions=True)
	frappe.db.commit()

def toggle_2fa_all_role(state=None):
	'''Enable or disable 2fa for 'all' role on the system.'''
	all_role = frappe.get_doc('Role','All')
	if state == None:
		state = False if all_role.two_factor_auth == True else False
	if state not in [True, False]: return
	all_role.two_factor_auth = cint(state)
	all_role.save(ignore_permissions=True)
	frappe.db.commit()

def get_otp(user):
	otp_secret = get_otpsecret_for_(user)
	otp = pyotp.TOTP(otp_secret)
	return otp.now()
