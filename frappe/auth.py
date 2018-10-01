# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import datetime

from frappe import _
import frappe
import frappe.database
import frappe.utils
from frappe.utils import cint, flt, get_datetime, datetime
import frappe.utils.user
from frappe import conf
from frappe.sessions import Session, clear_sessions, delete_session
from frappe.modules.patch_handler import check_session_stopped
from frappe.translate import get_lang_code
from frappe.utils.password import check_password, delete_login_failed_cache
from frappe.core.doctype.activity_log.activity_log import add_authentication_log
from frappe.twofactor import (should_run_2fa, authenticate_for_2factor,
	confirm_otp_token, get_cached_user_pass)

from six.moves.urllib.parse import quote


class HTTPRequest:
	def __init__(self):
		# Get Environment variables
		self.domain = frappe.request.host
		if self.domain and self.domain.startswith('www.'):
			self.domain = self.domain[4:]

		if frappe.get_request_header('X-Forwarded-For'):
			frappe.local.request_ip = (frappe.get_request_header('X-Forwarded-For').split(",")[0]).strip()

		elif frappe.get_request_header('REMOTE_ADDR'):
			frappe.local.request_ip = frappe.get_request_header('REMOTE_ADDR')

		else:
			frappe.local.request_ip = '127.0.0.1'

		# language
		self.set_lang()

		# load cookies
		frappe.local.cookie_manager = CookieManager()

		# set db
		self.connect()

		# login
		frappe.local.login_manager = LoginManager()

		if frappe.form_dict._lang:
			lang = get_lang_code(frappe.form_dict._lang)
			if lang:
				frappe.local.lang = lang

		self.validate_csrf_token()

		# write out latest cookies
		frappe.local.cookie_manager.init_cookies()

		# check status
		check_session_stopped()

	def validate_csrf_token(self):
		if frappe.local.request and frappe.local.request.method in ("POST", "PUT", "DELETE"):
			if not frappe.local.session: return
			if not frappe.local.session.data.csrf_token \
				or frappe.local.session.data.device=="mobile" \
				or frappe.conf.get('ignore_csrf', None):
				# not via boot
				return

			csrf_token = frappe.get_request_header("X-Frappe-CSRF-Token")
			if not csrf_token and "csrf_token" in frappe.local.form_dict:
				csrf_token = frappe.local.form_dict.csrf_token
				del frappe.local.form_dict["csrf_token"]

			if frappe.local.session.data.csrf_token != csrf_token:
				frappe.local.flags.disable_traceback = True
				frappe.throw(_("Invalid Request"), frappe.CSRFTokenError)

	def set_lang(self):
		from frappe.translate import guess_language
		frappe.local.lang = guess_language()

	def get_db_name(self):
		"""get database name from conf"""
		return conf.db_name

	def connect(self, ac_name = None):
		"""connect to db, from ac_name or db_name"""
		frappe.local.db = frappe.database.get_db(user = self.get_db_name(), \
			password = getattr(conf, 'db_password', ''))

class LoginManager:
	def __init__(self):
		self.user = None
		self.info = None
		self.full_name = None
		self.user_type = None

		if frappe.local.form_dict.get('cmd')=='login' or frappe.local.request.path=="/api/method/login":
			if self.login()==False: return
			self.resume = False

			# run login triggers
			self.run_trigger('on_session_creation')
		else:
			try:
				self.resume = True
				self.make_session(resume=True)
				self.get_user_info()
				self.set_user_info(resume=True)
			except AttributeError:
				self.user = "Guest"
				self.get_user_info()
				self.make_session()
				self.set_user_info()

	def login(self):
		# clear cache
		frappe.clear_cache(user = frappe.form_dict.get('usr'))
		user, pwd = get_cached_user_pass()
		self.authenticate(user=user, pwd=pwd)
		if should_run_2fa(self.user):
			authenticate_for_2factor(self.user)
			if not confirm_otp_token(self):
				return False
		self.post_login()

	def post_login(self):
		self.run_trigger('on_login')
		self.validate_ip_address()
		self.validate_hour()
		self.get_user_info()
		self.make_session()
		self.set_user_info()

	def get_user_info(self, resume=False):
		self.info = frappe.db.get_value("User", self.user,
			["user_type", "first_name", "last_name", "user_image"], as_dict=1)

		self.user_type = self.info.user_type

	def set_user_info(self, resume=False):
		# set sid again
		frappe.local.cookie_manager.init_cookies()

		self.full_name = " ".join(filter(None, [self.info.first_name,
			self.info.last_name]))

		if self.info.user_type=="Website User":
			frappe.local.cookie_manager.set_cookie("system_user", "no")
			if not resume:
				frappe.local.response["message"] = "No App"
				frappe.local.response["home_page"] = get_website_user_home_page(self.user)
		else:
			frappe.local.cookie_manager.set_cookie("system_user", "yes")
			if not resume:
				frappe.local.response['message'] = 'Logged In'
				frappe.local.response["home_page"] = "/desk"

		if not resume:
			frappe.response["full_name"] = self.full_name

		# redirect information
		redirect_to = frappe.cache().hget('redirect_after_login', self.user)
		if redirect_to:
			frappe.local.response["redirect_to"] = redirect_to
			frappe.cache().hdel('redirect_after_login', self.user)


		frappe.local.cookie_manager.set_cookie("full_name", self.full_name)
		frappe.local.cookie_manager.set_cookie("user_id", self.user)
		frappe.local.cookie_manager.set_cookie("user_image", self.info.user_image or "")

	def make_session(self, resume=False):
		# start session
		frappe.local.session_obj = Session(user=self.user, resume=resume,
			full_name=self.full_name, user_type=self.user_type)

		# reset user if changed to Guest
		self.user = frappe.local.session_obj.user
		frappe.local.session = frappe.local.session_obj.data
		self.clear_active_sessions()

	def clear_active_sessions(self):
		"""Clear other sessions of the current user if `deny_multiple_sessions` is not set"""
		if not (cint(frappe.conf.get("deny_multiple_sessions")) or cint(frappe.db.get_system_setting('deny_multiple_sessions'))):
			return

		if frappe.session.user != "Guest":
			clear_sessions(frappe.session.user, keep_current=True)

	def authenticate(self, user=None, pwd=None):
		if not (user and pwd):
			user, pwd = frappe.form_dict.get('usr'), frappe.form_dict.get('pwd')
		if not (user and pwd):
			self.fail(_('Incomplete login details'), user=user)

		if cint(frappe.db.get_value("System Settings", "System Settings", "allow_login_using_mobile_number")):
			user = frappe.db.get_value("User", filters={"mobile_no": user}, fieldname="name") or user

		if cint(frappe.db.get_value("System Settings", "System Settings", "allow_login_using_user_name")):
			user = frappe.db.get_value("User", filters={"username": user}, fieldname="name") or user

		self.check_if_enabled(user)
		self.user = self.check_password(user, pwd)

	def check_if_enabled(self, user):
		"""raise exception if user not enabled"""
		doc = frappe.get_doc("System Settings")
		if cint(doc.allow_consecutive_login_attempts) > 0:
			check_consecutive_login_attempts(user, doc)

		if user=='Administrator': return
		if not cint(frappe.db.get_value('User', user, 'enabled')):
			self.fail('User disabled or missing', user=user)

	def check_password(self, user, pwd):
		"""check password"""
		try:
			# returns user in correct case
			return check_password(user, pwd)
		except frappe.AuthenticationError:
			self.update_invalid_login(user)
			self.fail('Incorrect password', user=user)

	def fail(self, message, user=None):
		if not user:
			user = _('Unknown User')
		frappe.local.response['message'] = message
		add_authentication_log(message, user, status="Failed")
		frappe.db.commit()
		raise frappe.AuthenticationError

	def update_invalid_login(self, user):
		last_login_tried = get_last_tried_login_data(user)

		failed_count = 0
		if last_login_tried > get_datetime():
			failed_count = get_login_failed_count(user)

		frappe.cache().hset('login_failed_count', user, failed_count + 1)

	def run_trigger(self, event='on_login'):
		for method in frappe.get_hooks().get(event, []):
			frappe.call(frappe.get_attr(method), login_manager=self)

	def validate_ip_address(self):
		"""check if IP Address is valid"""
		user = frappe.get_doc("User", self.user)
		ip_list = user.get_restricted_ip_list()
		if not ip_list:
			return

		bypass_restrict_ip_check = 0
		# check if two factor auth is enabled
		enabled = int(frappe.get_system_settings('enable_two_factor_auth') or 0)
		if enabled:
			#check if bypass restrict ip is enabled for all users
			bypass_restrict_ip_check = int(frappe.get_system_settings('bypass_restrict_ip_check_if_2fa_enabled') or 0)
			if not bypass_restrict_ip_check:
				#check if bypass restrict ip is enabled for login user
				bypass_restrict_ip_check = int(frappe.db.get_value('User', self.user, 'bypass_restrict_ip_check_if_2fa_enabled') or 0)
		for ip in ip_list:
			if frappe.local.request_ip.startswith(ip) or bypass_restrict_ip_check:
				return

		frappe.throw(_("Not allowed from this IP Address"), frappe.AuthenticationError)

	def validate_hour(self):
		"""check if user is logging in during restricted hours"""
		login_before = int(frappe.db.get_value('User', self.user, 'login_before', ignore=True) or 0)
		login_after = int(frappe.db.get_value('User', self.user, 'login_after', ignore=True) or 0)

		if not (login_before or login_after):
			return

		from frappe.utils import now_datetime
		current_hour = int(now_datetime().strftime('%H'))

		if login_before and current_hour > login_before:
			frappe.throw(_("Login not allowed at this time"), frappe.AuthenticationError)

		if login_after and current_hour < login_after:
			frappe.throw(_("Login not allowed at this time"), frappe.AuthenticationError)

	def login_as_guest(self):
		"""login as guest"""
		self.login_as("Guest")

	def login_as(self, user):
		self.user = user
		self.post_login()

	def logout(self, arg='', user=None):
		if not user: user = frappe.session.user
		self.run_trigger('on_logout')

		if user == frappe.session.user:
			delete_session(frappe.session.sid, user=user, reason="User Manually Logged Out")
			self.clear_cookies()
		else:
			clear_sessions(user)

	def clear_cookies(self):
		clear_cookies()

class CookieManager:
	def __init__(self):
		self.cookies = {}
		self.to_delete = []

	def init_cookies(self):
		if not frappe.local.session.get('sid'): return

		# sid expires in 3 days
		expires = datetime.datetime.now() + datetime.timedelta(days=3)
		if frappe.session.sid:
			self.cookies["sid"] = {"value": frappe.session.sid, "expires": expires}
		if frappe.session.session_country:
			self.cookies["country"] = {"value": frappe.session.get("session_country")}

	def set_cookie(self, key, value, expires=None):
		self.cookies[key] = {"value": value, "expires": expires}

	def delete_cookie(self, to_delete):
		if not isinstance(to_delete, (list, tuple)):
			to_delete = [to_delete]

		self.to_delete.extend(to_delete)

	def flush_cookies(self, response):
		for key, opts in self.cookies.items():
			response.set_cookie(key, quote((opts.get("value") or "").encode('utf-8')),
				expires=opts.get("expires"))

		# expires yesterday!
		expires = datetime.datetime.now() + datetime.timedelta(days=-1)
		for key in set(self.to_delete):
			response.set_cookie(key, "", expires=expires)


@frappe.whitelist()
def get_logged_user():
	return frappe.session.user

def clear_cookies():
	if hasattr(frappe.local, "session"):
		frappe.session.sid = ""
	frappe.local.cookie_manager.delete_cookie(["full_name", "user_id", "sid", "user_image", "system_user"])

def get_website_user_home_page(user):
	home_page_method = frappe.get_hooks('get_website_user_home_page')
	if home_page_method:
		home_page = frappe.get_attr(home_page_method[-1])(user)
		return '/' + home_page.strip('/')
	elif frappe.get_hooks('website_user_home_page'):
		return '/' + frappe.get_hooks('website_user_home_page')[-1].strip('/')
	else:
		return '/me'

def get_last_tried_login_data(user, get_last_login=False):
	locked_account_time = frappe.cache().hget('locked_account_time', user)
	if get_last_login and locked_account_time:
		return locked_account_time

	last_login_tried = frappe.cache().hget('last_login_tried', user)
	if not last_login_tried or last_login_tried < get_datetime():
		last_login_tried = get_datetime() + datetime.timedelta(seconds=60)

	frappe.cache().hset('last_login_tried', user, last_login_tried)

	return last_login_tried

def get_login_failed_count(user):
	return cint(frappe.cache().hget('login_failed_count', user)) or 0

def check_consecutive_login_attempts(user, doc):
	login_failed_count = get_login_failed_count(user)
	last_login_tried = (get_last_tried_login_data(user, True)
		+ datetime.timedelta(seconds=doc.allow_login_after_fail))

	if login_failed_count >= cint(doc.allow_consecutive_login_attempts):
		locked_account_time = frappe.cache().hget('locked_account_time', user)
		if not locked_account_time:
			frappe.cache().hset('locked_account_time', user, get_datetime())

		if last_login_tried > get_datetime():
			frappe.throw(_("Your account has been locked and will resume after {0} seconds")
				.format(doc.allow_login_after_fail), frappe.SecurityException)
		else:
			delete_login_failed_cache(user)
