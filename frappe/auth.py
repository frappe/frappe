# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import datetime

from frappe import _
import frappe
import frappe.database
import frappe.utils
from frappe.utils import cint, flt, get_datetime, datetime, date_diff, today
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
		if self.force_user_to_reset_password():
			doc = frappe.get_doc("User", self.user)
			frappe.local.response["redirect_to"] = doc.reset_password(send_email=False, password_expired=True)
			frappe.local.response["message"] = "Password Reset"
			return False

		if should_run_2fa(self.user):
			authenticate_for_2factor(self.user)
			if not confirm_otp_token(self):
				return False
		self.post_login()

	def post_login(self):
		self.run_trigger('on_login')
		validate_ip_address(self.user)
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

	def authenticate(self, user = None, pwd = None):
		from frappe.core.doctype.user.user import User

		if not (user and pwd):
			user, pwd = frappe.form_dict.get('usr'), frappe.form_dict.get('pwd')
		if not (user and pwd):
			self.fail(_('Incomplete login details'), user=user)

		# Ignore password check if tmp_id is set, 2FA takes care of authentication.
		validate_password = not bool(frappe.form_dict.get('tmp_id'))
		user = User.find_by_credentials(user, pwd, validate_password=validate_password)

		if not user:
			self.fail('Invalid login credentials')

		sys_settings = frappe.get_doc("System Settings")
		track_login_attempts = (sys_settings.allow_consecutive_login_attempts >0)

		tracker_kwargs = {}
		if track_login_attempts:
			tracker_kwargs['lock_interval'] = sys_settings.allow_login_after_fail
			tracker_kwargs['max_consecutive_login_attempts'] = sys_settings.allow_consecutive_login_attempts

		tracker = LoginAttemptTracker(user.name, **tracker_kwargs)

		if track_login_attempts and not tracker.is_user_allowed():
			frappe.throw(_("Your account has been locked and will resume after {0} seconds")
				.format(sys_settings.allow_login_after_fail), frappe.SecurityException)

		if not user.is_authenticated:
			tracker.add_failure_attempt()
			self.fail('Invalid login credentials', user=user.name)
		elif not (user.name == 'Administrator' or user.enabled):
			tracker.add_failure_attempt()
			self.fail('User disabled or missing', user=user.name)
		else:
			tracker.add_success_attempt()
		self.user = user.name

	def force_user_to_reset_password(self):
		if not self.user:
			return

		from frappe.core.doctype.user.user import STANDARD_USERS
		if self.user in STANDARD_USERS:
			return False

		reset_pwd_after_days = cint(frappe.db.get_single_value("System Settings",
			"force_user_to_reset_password"))

		if reset_pwd_after_days:
			last_password_reset_date = frappe.db.get_value("User",
				self.user, "last_password_reset_date")  or today()

			last_pwd_reset_days = date_diff(today(), last_password_reset_date)

			if last_pwd_reset_days > reset_pwd_after_days:
				return True

	def check_password(self, user, pwd):
		"""check password"""
		try:
			# returns user in correct case
			return check_password(user, pwd)
		except frappe.AuthenticationError:
			self.fail('Incorrect password', user=user)

	def fail(self, message, user=None):
		if not user:
			user = _('Unknown User')
		frappe.local.response['message'] = message
		add_authentication_log(message, user, status="Failed")
		frappe.db.commit()
		raise frappe.AuthenticationError

	def run_trigger(self, event='on_login'):
		for method in frappe.get_hooks().get(event, []):
			frappe.call(frappe.get_attr(method), login_manager=self)

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

def validate_ip_address(user):
	"""check if IP Address is valid"""
	user = frappe.get_cached_doc("User", user) if not frappe.flags.in_test else frappe.get_doc("User", user)
	ip_list = user.get_restricted_ip_list()
	if not ip_list:
		return

	system_settings = frappe.get_cached_doc("System Settings") if not frappe.flags.in_test else frappe.get_single("System Settings")
	# check if bypass restrict ip is enabled for all users
	bypass_restrict_ip_check = system_settings.bypass_restrict_ip_check_if_2fa_enabled

	# check if two factor auth is enabled
	if system_settings.enable_two_factor_auth and not bypass_restrict_ip_check:
		# check if bypass restrict ip is enabled for login user
		bypass_restrict_ip_check = user.bypass_restrict_ip_check_if_2fa_enabled

	for ip in ip_list:
		if frappe.local.request_ip.startswith(ip) or bypass_restrict_ip_check:
			return

	frappe.throw(_("Access not allowed from this IP Address"), frappe.AuthenticationError)


class LoginAttemptTracker(object):
	"""Track login attemts of a user.

	Lock the account for s number of seconds if there have been n consecutive unsuccessful attempts to log in.
	"""
	def __init__(self, user_name, max_consecutive_login_attempts=3, lock_interval=5*60):
		""" Initialize the tracker.

		:param user_name: Name of the loggedin user
		:param max_consecutive_login_attempts: Maximum allowed consecutive failed login attempts
		:param lock_interval: Locking interval incase of maximum failed attempts
		"""
		self.user_name = user_name
		self.lock_interval = datetime.timedelta(seconds=lock_interval)
		self.max_failed_logins = max_consecutive_login_attempts

	@property
	def login_failed_count(self):
		return frappe.cache().hget('login_failed_count', self.user_name)

	@login_failed_count.setter
	def login_failed_count(self, count):
		frappe.cache().hset('login_failed_count', self.user_name, count)

	@login_failed_count.deleter
	def login_failed_count(self):
		frappe.cache().hdel('login_failed_count', self.user_name)

	@property
	def login_failed_time(self):
		"""First failed login attempt time within lock interval.

		For every user we track only First failed login attempt time within lock interval of time.
		"""
		return frappe.cache().hget('login_failed_time', self.user_name)

	@login_failed_time.setter
	def login_failed_time(self, timestamp):
		frappe.cache().hset('login_failed_time', self.user_name, timestamp)

	@login_failed_time.deleter
	def login_failed_time(self):
		frappe.cache().hdel('login_failed_time', self.user_name)

	def add_failure_attempt(self):
		""" Log user failure attempts into the system.

		Increase the failure count if new failure is with in current lock interval time period, if not reset the login failure count.
		"""
		login_failed_time = self.login_failed_time
		login_failed_count = self.login_failed_count # Consecutive login failure count
		current_time = get_datetime()

		if not (login_failed_time and login_failed_count):
			login_failed_time, login_failed_count = current_time, 0

		if login_failed_time + self.lock_interval > current_time:
			login_failed_count += 1
		else:
			login_failed_time, login_failed_count = current_time, 1

		self.login_failed_time = login_failed_time
		self.login_failed_count = login_failed_count

	def add_success_attempt(self):
		"""Reset login failures.
		"""
		del self.login_failed_count
		del self.login_failed_time

	def is_user_allowed(self):
		"""Is user allowed to login

		User is not allowed to login if login failures are greater than threshold within in lock interval from first login failure.
		"""
		login_failed_time = self.login_failed_time
		login_failed_count = self.login_failed_count or 0
		current_time = get_datetime()

		if login_failed_time and login_failed_time + self.lock_interval > current_time and login_failed_count > self.max_failed_logins:
			return False
		return True
