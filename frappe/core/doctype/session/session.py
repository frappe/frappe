# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import (date_diff, today)
from frappe.model.document import Document
from frappe.utils.password import validate_password
from six.moves.urllib.parse import unquote
from frappe import _
from datetime import timedelta
from frappe.twofactor import (should_run_2fa, authenticate_for_2factor,
	confirm_otp_token, get_cached_user_pass)

class SessionExpiredError(frappe.AuthenticationError): pass
class InvalidIPError(frappe.AuthenticationError): pass
class InvalidLoginHour(frappe.AuthenticationError): pass
class TooManyFailedLogins(frappe.AuthenticationError): pass

# TODO
# [x] - stop simultaneous logins
# [x] - support for 2FA
# [x] - forced password change
# [ ] - build response
# [ ] - custom home page
# [ ] - expiry
# [ ] - cookies
# [ ] - cache
# [ ] - boot

def get_session(sid=None):
	'''Return the session object from the `sid` parameter or cookie'''
	if not sid:
		sid = get_session_id()

	if frappe.db.exists('Session', dict(name=sid, status='Active')):
		# active session exists, return it
		session = frappe.get_doc('Session', sid)
		session.check_expiry()
		return session
	else:
		raise SessionExpiredError

def login(user=None, password=None):
	return frappe.get_doc(dict(doctype='Session')).login(user, password)

def get_session_id():
	sid = frappe.cstr(frappe.form_dict.get('sid'))
	if not sid and frappe.request:
		sid = unquote(frappe.request.cookies.get('sid', 'Guest'))

	return sid

class Session(Document):
	def login(self, user, password):
		self.reset_password = False
		self.resume_session = False

		self.set_user_and_password(user, password)
		self.check_if_enabled()
		self.check_if_locked_due_to_multiple_failed_attempts()
		self.validate_twofactor()
		self.validate_password()
		self.validate_ip_address()
		self.validate_hour()
		self.deny_multiple_sessions()
		self.force_user_to_reset_password()
		self.build_response()

		return self

	def resume(self):
		self.resume_session = True
		self.build_data()
		self.set_cookies()
		self.set_response()
		self.set_redirect()

	def build_response(self):
		if self.reset_password:
			self.redirect_to_reset_password()
		else:
			self.build_data()
			self.set_cookies()
			self.set_response()
			self.set_redirect()

	def extend_expiry(self):
		pass

	def check_expiry(self):
		pass

	def build_data(self):
		user = self.user_doc
		self.info = dict(
			first_name = user.first_name,
			last_name = user.last_name,
			user_type = user.user_type,
			user_image = user.user_image
		)
		self.user_type = user.user_type
		self.full_name = " ".join(filter(None, [self.info.first_name,
			self.info.last_name]))

	def logout(self):
		self.status = 'Logged Out'
		self.save(force=True)

	def fail(self, message):
		'''Log status, update session status as failed and commit'''
		frappe.local.response['message'] = message
		self.status = 'Login Failed'
		self.save(force=True)
		frappe.db.commit()
		raise frappe.AuthenticationError

	def check_if_enabled(self):
		'''Check if user is enabled or Administrator'''

		# Administrator is always enabled
		if self.user=='Administrator': return

		if not frappe.db.get_value('User', self.user, 'enabled'):
			self.user = None
			self.fail('User disabled or missing')

	def check_if_locked_due_to_multiple_failed_attempts(self):
		allowed_attempts = frappe.get_system_settings('allow_consecutive_login_attempts')
		if allowed_attempts:
			cool_down_seconds = frappe.get_system_settings('allow_login_after_fail')
			# restrictions exist, find out how many failed attempts in the last X seconds
			failed_attempts = frappe.db.count('Session',
				dict(
					user=self.user,
					status='Login Failed',
					creation=['>', frappe.utils.now_datetime() - timedelta(seconds = cool_down_seconds)]
				))

			if failed_attempts >= allowed_attempts:
				frappe.throw(_("Your account has been locked and will resume after {0} seconds").format(cool_down_seconds), TooManyFailedLogins)

	def validate_password(self):
		# check if password is valid
		if not validate_password(self.user, self.password):
			self.fail('Incorrect User or Password')

		self.status = 'Active'
		self.insert(force=True)

	def deny_multiple_sessions(self):
		'''Logout all parallel sessions other than this one and others allowed'''
		if not (frappe.cint(frappe.conf.get("deny_multiple_sessions")) or frappe.cint(frappe.db.get_system_setting('deny_multiple_sessions'))):
			return

		additional_sessions_allowed = (self.user_doc.simultaneous_sessions or 1) - 1

		# get all active sessions except this one
		for session in frappe.get_all('Session', dict(
			user=self.user,
			status='Active',
			name=('!=', self.name)),
			device = self.device,
			order_by='creation desc'):

			if additional_sessions_allowed:
				# additional sessions allowed, so let this be
				# and reduce count by 1
				additional_sessions_allowed -= 1
				continue

			self.expire_session(session.name)

	def expire_session(self, name):
		session = frappe.get_doc('Session', name)
		session.status = 'Expired'
		session.save(force=True)

	def validate_ip_address(self):
		restricted_ip_list = self.user_doc.get_restricted_ip_list()

		if not restricted_ip_list or self.is_ip_check_bypassed_if_two_factor_is_enabled():
			# unrestricted IP access
			return

		for ip in self.user_doc.get_restricted_ip_list():
			if frappe.local.request_ip.startswith(ip):
				# valid IP found, quit
				return

		frappe.throw(_("Not allowed from this IP Address"), InvalidIPError)

	def is_ip_check_bypassed_if_two_factor_is_enabled(self):
		# user may be bypassed ip checks if two factor is enabled
		bypassed = False
		if frappe.get_system_settings('enable_two_factor_auth'):
			if frappe.get_system_settings('bypass_restrict_ip_check_if_2fa_enabled'):
				# bypassed globally
				return True

			if frappe.db.get_value('User', self.user, 'bypass_restrict_ip_check_if_2fa_enabled'):
				# user bypassed
				return True

		return bypassed

	def set_user_and_password(self, user=None, password=None):
		self.user, self.password = user, password

		# password set via two factor
		self.set_user_from_two_factor()

		# user and password passed via request parameters
		if not self.user: self.user = frappe.form_dict.get('usr')
		if not self.password: self.password = frappe.form_dict.get('pwd')

		self.set_alternate_username()

	def validate_twofactor(self):
		if should_run_2fa(self.user):
			authenticate_for_2factor(self.user)
			if not confirm_otp_token(self):
				return False

	def set_user_from_two_factor(self):
		tmp_id = frappe.form_dict.get('tmp_id')
		if tmp_id:
			self.user = frappe.safe_decode(frappe.cache().get(tmp_id+'_usr'))
			self.password = frappe.safe_decode(frappe.cache().get(tmp_id+'_pwd'))

	def validate_hour(self):
		"""check if user is logging in during restricted hours"""
		user = self.user_doc

		if not (user.login_before or user.login_after):
			return

		from frappe.utils import now_datetime
		current_hour = frappe.flags.test_current_hour or int(now_datetime().strftime('%H'))

		if ((user.login_before and current_hour > user.login_before)
			or (user.login_after and current_hour < user.login_after)):
			frappe.throw(_("Login not allowed at this time"), InvalidLoginHour)

	def force_user_to_reset_password(self):
		if not self.user:
			return

		reset_pwd_after_days = frappe.get_system_settings('force_user_to_reset_password')

		if reset_pwd_after_days:
			last_password_reset_date = frappe.db.get_value("User",
				self.user, "last_password_reset_date")  or today()

			last_pwd_reset_days = date_diff(today(), last_password_reset_date)

			if last_pwd_reset_days > reset_pwd_after_days:
				self.reset_password = True

	def set_alternate_username(self):
		# replace the mobile number with user id
		if frappe.get_system_settings('allow_login_using_mobile_number'):
			self.user = frappe.db.get_value("User", filters={"mobile_no": self.user}) or self.user

		# replace user id with custom username
		if frappe.get_system_settings('allow_login_using_user_name'):
			self.user = frappe.db.get_value("User", filters={"username": self.user}) or self.user

	def redirect_to_reset_password(self):
		frappe.local.response["redirect_to"] = self.user_doc.reset_password(send_email=False, password_expired=True)
		frappe.local.response["message"] = "Password Reset"

	def set_cookies(self):
		'''set addtional cookies with user information'''
		frappe.local.cookie_manager.init_cookies()

		frappe.local.cookie_manager.set_cookie("system_user",
			"no" if self.user_type=='Website User' else "yes")

		frappe.local.cookie_manager.set_cookie("full_name", self.full_name)
		frappe.local.cookie_manager.set_cookie("user_id", self.user)
		frappe.local.cookie_manager.set_cookie("user_image", self.info.user_image or "")

	def set_response(self):
		'''build response parameters with status and route for home page'''
		if not self.resume_session:
			if self.user_type=="Website User":
				frappe.local.response["message"] = "No App"
				frappe.local.response["home_page"] = self.get_website_user_home_page()
			else:
				frappe.local.response['message'] = 'Logged In'
				frappe.local.response["home_page"] = "/desk"

			frappe.response["full_name"] = self.full_name

	def set_redirect(self):
		'''If user is to be redirected to another page after loging via `?redirect_to=[route]'''
		# redirect information
		redirect_to = frappe.cache().hget('redirect_after_login', self.user)
		if redirect_to:
			frappe.local.response["redirect_to"] = redirect_to
			frappe.cache().hdel('redirect_after_login', self.user)

	def get_website_user_home_page(self):
		home_page_method = frappe.get_hooks('get_website_user_home_page')
		if home_page_method:
			home_page = frappe.get_attr(home_page_method[-1])(self.user)
			return '/' + home_page.strip('/')
		elif frappe.get_hooks('website_user_home_page'):
			return '/' + frappe.get_hooks('website_user_home_page')[-1].strip('/')
		else:
			return '/me'

	def trigger_event(self, event):
		for method in frappe.get_hooks().get(event, []):
			frappe.call(frappe.get_attr(method), login_manager=self)

	def get_status(self):
		'''get latest status from the database'''
		return frappe.db.get_value('Session', self.name, 'status')

	@property
	def user_doc(self):
		return frappe.get_cached_doc('User', self.user)


