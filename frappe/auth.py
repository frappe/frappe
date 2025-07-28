# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See LICENSE
import base64
import binascii
from urllib.parse import quote, unquote, urlencode, urlparse

from werkzeug.wrappers import Response

import frappe
import frappe.database
import frappe.utils
import frappe.utils.user
from frappe import _
from frappe.apps import get_default_path
from frappe.core.doctype.activity_log.activity_log import add_authentication_log
from frappe.sessions import Session, clear_sessions, delete_session, get_expiry_in_seconds
from frappe.translate import get_language
from frappe.twofactor import (
	authenticate_for_2factor,
	confirm_otp_token,
	get_cached_user_pass,
	should_run_2fa,
)
from frappe.utils import cint, date_diff, datetime, get_datetime, today
from frappe.utils.password import check_password, get_decrypted_password
from frappe.website.utils import get_home_page

SAFE_HTTP_METHODS = frozenset(("GET", "HEAD", "OPTIONS"))
UNSAFE_HTTP_METHODS = frozenset(("POST", "PUT", "DELETE", "PATCH"))
MAX_PASSWORD_SIZE = 512


class HTTPRequest:
	def __init__(self):
		# set frappe.local.request_ip
		self.set_request_ip()

		# load cookies
		self.set_cookies()

		# login and start/resume user session
		self.set_session()

		# set request language
		self.set_lang()

		# match csrf token from current session
		self.validate_csrf_token()

		# write out latest cookies
		frappe.local.cookie_manager.init_cookies()

	@property
	def domain(self):
		if not getattr(self, "_domain", None):
			self._domain = frappe.request.host
			if self._domain and self._domain.startswith("www."):
				self._domain = self._domain[4:]

		return self._domain

	def set_request_ip(self):
		if frappe.get_request_header("X-Forwarded-For"):
			frappe.local.request_ip = (frappe.get_request_header("X-Forwarded-For").split(",", 1)[0]).strip()

		elif frappe.get_request_header("REMOTE_ADDR"):
			frappe.local.request_ip = frappe.get_request_header("REMOTE_ADDR")

		else:
			frappe.local.request_ip = "127.0.0.1"

	def set_cookies(self):
		frappe.local.cookie_manager = CookieManager()

	def set_session(self):
		frappe.local.login_manager = LoginManager()

	def validate_csrf_token(self):
		if (
			not frappe.request
			or frappe.request.method not in UNSAFE_HTTP_METHODS
			or frappe.conf.ignore_csrf
			or not frappe.session
			or not (saved_token := frappe.session.data.csrf_token)
			or (
				(frappe.get_request_header("X-Frappe-CSRF-Token") or frappe.form_dict.pop("csrf_token", None))
				== saved_token
			)
			or self.is_allowed_referrer()
		):
			return

		frappe.flags.disable_traceback = True
		frappe.throw(_("Invalid Request"), frappe.CSRFTokenError)

	def set_lang(self):
		frappe.local.lang = get_language()

	def is_allowed_referrer(self):
		referrer = frappe.get_request_header("Referer")
		origin = frappe.get_request_header("Origin")

		# Get the list of allowed referrers from cache or configuration
		allowed_referrers = frappe.cache.get_value(
			"allowed_referrers",
			generator=lambda: frappe.conf.get("allowed_referrers", []),
		)

		# Check if the referrer or origin is in the allowed list
		return (referrer and any(referrer.startswith(allowed) for allowed in allowed_referrers)) or (
			origin and any(origin == allowed for allowed in allowed_referrers)
		)


class LoginManager:
	__slots__ = ("full_name", "info", "resume", "user", "user_lang", "user_type")

	def __init__(self):
		self.user = None
		self.info = None
		self.full_name = None
		self.user_type = None

		if frappe.local.form_dict.get("cmd") == "login" or frappe.local.request.path == "/api/method/login":
			if self.login() is False:
				return
			self.resume = False
		else:
			try:
				self.resume = True
				self.make_session(resume=True)
				self.get_user_info()
				self.set_user_info(resume=True)
			except (AttributeError, frappe.DoesNotExistError):
				self.user = "Guest"
				self.get_user_info()
				self.make_session()
				self.set_user_info()

	def login(self):
		self.run_trigger("before_login")

		if frappe.get_system_settings("disable_user_pass_login"):
			frappe.throw(_("Login with username and password is not allowed."), frappe.AuthenticationError)

		# clear cache
		frappe.clear_cache(user=frappe.form_dict.get("usr"))
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
		frappe.form_dict.pop("pwd", None)
		self.post_login()

	def post_login(self, session_end: str | None = None, audit_user: str | None = None):
		self.run_trigger("on_login")
		validate_ip_address(self.user)
		self.validate_hour()
		self.get_user_info()
		self.make_session(session_end=session_end, audit_user=audit_user)
		self.setup_boot_cache()
		self.set_user_info()

	def get_user_info(self):
		self.info = frappe.get_cached_value(
			"User", self.user, ["user_type", "first_name", "last_name", "user_image"], as_dict=1
		)
		self.user_type = self.info.user_type

	def setup_boot_cache(self):
		frappe.cache_manager.build_table_count_cache()
		frappe.cache_manager.build_domain_restricted_doctype_cache()
		frappe.cache_manager.build_domain_restricted_page_cache()

	def set_user_info(self, resume=False):
		# set sid again
		frappe.local.cookie_manager.init_cookies()

		self.full_name = " ".join(filter(None, [self.info.first_name, self.info.last_name]))

		if self.info.user_type == "Website User":
			frappe.local.cookie_manager.set_cookie("system_user", "no", deduplicate=True)
			if not resume:
				frappe.local.response["message"] = "No App"
				frappe.local.response["home_page"] = get_default_path() or "/" + get_home_page()
		else:
			frappe.local.cookie_manager.set_cookie("system_user", "yes", deduplicate=True)
			if not resume:
				frappe.local.response["message"] = "Logged In"
				frappe.local.response["home_page"] = get_default_path() or "/app"

		if not resume:
			frappe.response["full_name"] = self.full_name

		# redirect information
		if not resume and (redirect_to := frappe.cache.hget("redirect_after_login", self.user)):
			frappe.local.response["redirect_to"] = redirect_to
			frappe.cache.hdel("redirect_after_login", self.user)

		frappe.local.cookie_manager.set_cookie("full_name", self.full_name, deduplicate=True)
		frappe.local.cookie_manager.set_cookie("user_id", self.user, deduplicate=True)
		frappe.local.cookie_manager.set_cookie("user_image", self.info.user_image or "", deduplicate=True)
		frappe.local.cookie_manager.set_cookie("user_lang", frappe.local.lang, deduplicate=True)

	def clear_preferred_language(self):
		frappe.local.cookie_manager.delete_cookie("preferred_language")

	def make_session(
		self, resume: bool = False, session_end: str | None = None, audit_user: str | None = None
	):
		# start session
		frappe.local.session_obj = Session(
			user=self.user,
			resume=resume,
			full_name=self.full_name,
			user_type=self.user_type,
			session_end=session_end,
			audit_user=audit_user,
		)

		# reset user if changed to Guest
		self.user = frappe.local.session_obj.user
		frappe.local.session = frappe.local.session_obj.data
		self.clear_active_sessions()
		if not resume:
			self.run_trigger("on_session_creation")

	def clear_active_sessions(self):
		"""Clear other sessions of the current user if `deny_multiple_sessions` is not set"""
		if frappe.session.user == "Guest":
			return

		if not (
			cint(frappe.conf.get("deny_multiple_sessions"))
			or cint(frappe.db.get_system_setting("deny_multiple_sessions"))
		):
			return

		clear_sessions(frappe.session.user, keep_current=True)

	def authenticate(self, user: str | None = None, pwd: str | None = None):
		from frappe.core.doctype.user.user import User

		if not (user and pwd):
			user, pwd = frappe.form_dict.get("usr"), frappe.form_dict.get("pwd")
		if not (user and pwd):
			self.fail(_("Incomplete login details"), user=user)

		if len(pwd) > MAX_PASSWORD_SIZE:
			self.fail(_("Password size exceeded the maximum allowed size"), user=user)

		_raw_user_name = user
		user = User.find_by_credentials(user, pwd)

		ip_tracker = get_login_attempt_tracker(frappe.local.request_ip)
		if not user:
			ip_tracker and ip_tracker.add_failure_attempt()
			self.fail("Invalid login credentials", user=_raw_user_name)

		# Current login flow uses cached credentials for authentication while checking OTP.
		# Incase of OTP check, tracker for auth needs to be disabled(If not, it can remove tracker history as it is going to succeed anyway)
		# Tracker is activated for 2FA incase of OTP.
		ignore_tracker = should_run_2fa(user.name) and ("otp" in frappe.form_dict)
		user_tracker = None if ignore_tracker else get_login_attempt_tracker(user.name)

		if not user.is_authenticated:
			user_tracker and user_tracker.add_failure_attempt()
			ip_tracker and ip_tracker.add_failure_attempt()
			self.fail("Invalid login credentials", user=user.name)
		elif not (user.name == "Administrator" or user.enabled):
			user_tracker and user_tracker.add_failure_attempt()
			ip_tracker and ip_tracker.add_failure_attempt()
			self.fail("User disabled or missing", user=user.name)
		else:
			user_tracker and user_tracker.add_success_attempt()
			ip_tracker and ip_tracker.add_success_attempt()
		self.user = user.name

	def force_user_to_reset_password(self):
		if not self.user:
			return

		if self.user in frappe.STANDARD_USERS:
			return False

		reset_pwd_after_days = cint(frappe.get_system_settings("force_user_to_reset_password"))

		if reset_pwd_after_days:
			last_password_reset_date = (
				frappe.db.get_value("User", self.user, "last_password_reset_date") or today()
			)

			last_pwd_reset_days = date_diff(today(), last_password_reset_date)

			if last_pwd_reset_days > reset_pwd_after_days:
				return True

	def check_password(self, user, pwd):
		"""check password"""
		try:
			# return user in correct case
			return check_password(user, pwd)
		except frappe.AuthenticationError:
			self.fail("Incorrect password", user=user)

	def fail(self, message, user=None):
		if not user:
			user = _("Unknown User")
		frappe.local.response["message"] = message
		add_authentication_log(message, user, status="Failed")
		frappe.db.commit()
		raise frappe.AuthenticationError

	def run_trigger(self, event="on_login"):
		for method in frappe.get_hooks().get(event, []):
			frappe.call(frappe.get_attr(method), login_manager=self)

	def validate_hour(self):
		"""check if user is logging in during restricted hours"""
		login_before = cint(frappe.db.get_value("User", self.user, "login_before", ignore=True))
		login_after = cint(frappe.db.get_value("User", self.user, "login_after", ignore=True))

		if not (login_before or login_after):
			return

		from frappe.utils import now_datetime

		current_hour = int(now_datetime().strftime("%H"))

		if login_before and current_hour >= login_before:
			frappe.throw(_("Login not allowed at this time"), frappe.AuthenticationError)

		if login_after and current_hour < login_after:
			frappe.throw(_("Login not allowed at this time"), frappe.AuthenticationError)

	def login_as_guest(self):
		"""login as guest"""
		self.login_as("Guest")

	def login_as(self, user: str, session_end: str | None = None, audit_user: str | None = None):
		self.user = user
		self.post_login(session_end, audit_user)

	def impersonate(self, user):
		current_user = frappe.session.user
		session_data = frappe.local.session_obj.data.data
		self.login_as(user, session_end=session_data.session_end, audit_user=session_data.audit_user)
		# Flag this session as impersonated session, so other code can log this.
		frappe.local.session_obj.set_impersonated(current_user)

	def logout(self, arg="", user=None):
		if not user:
			user = frappe.session.user
		self.run_trigger("on_logout")

		if user == frappe.session.user:
			delete_session(frappe.session.sid, user=user, reason="User Manually Logged Out")
			self.clear_cookies()
			if frappe.request:
				self.login_as_guest()
		else:
			clear_sessions(user)

	def clear_cookies(self):
		clear_cookies()


class CookieManager:
	def __init__(self):
		self.cookies = {}
		self.to_delete = []

	def init_cookies(self):
		if not frappe.local.session.get("sid"):
			return

		if frappe.session.sid:
			self.set_cookie("sid", frappe.session.sid, max_age=get_expiry_in_seconds(), httponly=True)

	def set_cookie(
		self,
		key,
		value,
		expires=None,
		secure=False,
		httponly=False,
		samesite="Lax",
		max_age=None,
		deduplicate=False,
	):
		if not secure and hasattr(frappe.local, "request"):
			secure = frappe.local.request.scheme == "https"
		if (
			deduplicate
			and not (expires or max_age)
			and (request := getattr(frappe.local, "request", None))
			and unquote(request.cookies.get(key, "")) == value
		):
			return

		self.cookies[key] = {
			"value": value,
			"expires": expires,
			"secure": secure,
			"httponly": httponly,
			"samesite": samesite,
			"max_age": max_age,
		}

	def delete_cookie(self, to_delete):
		if not isinstance(to_delete, list | tuple):
			to_delete = [to_delete]

		self.to_delete.extend(to_delete)

	def flush_cookies(self, response: Response):
		for key, opts in self.cookies.items():
			response.set_cookie(
				key,
				quote((opts.get("value") or "").encode("utf-8")),
				expires=opts.get("expires"),
				secure=opts.get("secure"),
				httponly=opts.get("httponly"),
				samesite=opts.get("samesite"),
				max_age=opts.get("max_age"),
			)

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
	frappe.local.cookie_manager.delete_cookie(
		["full_name", "user_id", "sid", "user_image", "user_lang", "system_user"]
	)


def validate_ip_address(user):
	"""
	Method to check if the user has IP restrictions enabled, and if so is the IP address they are
	connecting from allowlisted.

	Certain methods called from our socketio backend need direct access, and so the IP is not
	checked for those
	"""
	if hasattr(frappe.local, "request") and frappe.local.request.path.startswith(
		"/api/method/frappe.realtime."
	):
		return True

	user_info = frappe.get_cached_doc("User", user)
	ip_list = user_info.get_restricted_ip_list()

	if not ip_list:
		return

	check_request_ip()
	for ip in ip_list:
		if frappe.local.request_ip.startswith(ip):
			return

	# check if bypass restrict ip is enabled for all users
	bypass_restrict_ip_check = frappe.get_system_settings("bypass_restrict_ip_check_if_2fa_enabled")

	# check if two factor auth is enabled
	if frappe.get_system_settings("enable_two_factor_auth") and not bypass_restrict_ip_check:
		# check if bypass restrict ip is enabled for login user
		bypass_restrict_ip_check = user_info.bypass_restrict_ip_check_if_2fa_enabled

	if bypass_restrict_ip_check:
		return

	frappe.throw(
		_("Access not allowed from this IP Address") + f": {frappe.local.request_ip}",
		frappe.AuthenticationError,
	)


def get_login_attempt_tracker(key: str, raise_locked_exception: bool = True):
	"""Get login attempt tracker instance.

	:param user_name: Name of the loggedin user
	:param raise_locked_exception: If set, raises an exception incase of user not allowed to login
	"""
	sys_settings = frappe.get_doc("System Settings")
	track_login_attempts = sys_settings.allow_consecutive_login_attempts > 0
	tracker_kwargs = {}

	if track_login_attempts:
		tracker_kwargs["lock_interval"] = sys_settings.allow_login_after_fail
		tracker_kwargs["max_consecutive_login_attempts"] = sys_settings.allow_consecutive_login_attempts

	tracker = LoginAttemptTracker(key, **tracker_kwargs)

	if raise_locked_exception and track_login_attempts and not tracker.is_user_allowed():
		frappe.throw(
			_("Your account has been locked and will resume after {0} seconds").format(
				sys_settings.allow_login_after_fail
			),
			frappe.SecurityException,
		)
	return tracker


class LoginAttemptTracker:
	"""Track login attemts of a user.

	Lock the account for s number of seconds if there have been n consecutive unsuccessful attempts to log in.
	"""

	def __init__(
		self,
		key: str,
		max_consecutive_login_attempts: int = 3,
		lock_interval: int = 5 * 60,
		*,
		user_name: str | None = None,
	):
		"""Initialize the tracker.

		:param user_name: Name of the loggedin user
		:param max_consecutive_login_attempts: Maximum allowed consecutive failed login attempts
		:param lock_interval: Locking interval incase of maximum failed attempts
		"""
		if user_name:
			from frappe.deprecation_dumpster import deprecation_warning

			deprecation_warning("unknown", "v17", "`username` parameter is deprecated, use `key` instead.")
		self.key = key or user_name
		self.lock_interval = datetime.timedelta(seconds=lock_interval)
		self.max_failed_logins = max_consecutive_login_attempts

	@property
	def login_failed_count(self):
		return frappe.cache.hget("login_failed_count", self.key)

	@login_failed_count.setter
	def login_failed_count(self, count):
		frappe.cache.hset("login_failed_count", self.key, count)

	@login_failed_count.deleter
	def login_failed_count(self):
		frappe.cache.hdel("login_failed_count", self.key)

	@property
	def login_failed_time(self):
		"""First failed login attempt time within lock interval.

		For every user we track only First failed login attempt time within lock interval of time.
		"""
		return frappe.cache.hget("login_failed_time", self.key)

	@login_failed_time.setter
	def login_failed_time(self, timestamp):
		frappe.cache.hset("login_failed_time", self.key, timestamp)

	@login_failed_time.deleter
	def login_failed_time(self):
		frappe.cache.hdel("login_failed_time", self.key)

	def add_failure_attempt(self):
		"""Log user failure attempts into the system.

		Increase the failure count if new failure is with in current lock interval time period, if not reset the login failure count.
		"""
		login_failed_time = self.login_failed_time
		login_failed_count = self.login_failed_count  # Consecutive login failure count
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
		"""Reset login failures."""
		del self.login_failed_count
		del self.login_failed_time

	def is_user_allowed(self) -> bool:
		"""Is user allowed to login

		User is not allowed to login if login failures are greater than threshold within in lock interval from first login failure.
		"""
		login_failed_time = self.login_failed_time
		login_failed_count = self.login_failed_count or 0
		current_time = get_datetime()

		if (
			login_failed_time
			and login_failed_time + self.lock_interval > current_time
			and login_failed_count > self.max_failed_logins
		):
			return False
		return True


def validate_auth():
	"""
	Authenticate and sets user for the request.
	"""
	authorization_header = frappe.get_request_header("Authorization", "").split(" ")

	if len(authorization_header) == 2:
		validate_oauth(authorization_header)
		validate_auth_via_api_keys(authorization_header)

	validate_auth_via_hooks()

	# If login via bearer, basic or keypair didn't work then authentication failed and we
	# should terminate here.
	if len(authorization_header) == 2 and frappe.session.user in ("", "Guest"):
		raise frappe.AuthenticationError


def validate_oauth(authorization_header):
	"""
	Authenticate request using OAuth and set session user

	Args:
	        authorization_header (list of str): The 'Authorization' header containing the prefix and token
	"""

	from frappe.integrations.oauth2 import get_oauth_server
	from frappe.oauth import get_url_delimiter

	if authorization_header[0].lower() != "bearer":
		return

	form_dict = frappe.local.form_dict
	token = authorization_header[1]
	req = frappe.request
	parsed_url = urlparse(req.url)
	access_token = {"access_token": token}
	uri = parsed_url.scheme + "://" + parsed_url.netloc + parsed_url.path + "?" + urlencode(access_token)
	http_method = req.method
	headers = req.headers
	body = req.get_data()
	if req.content_type and "multipart/form-data" in req.content_type:
		body = None

	try:
		required_scopes = frappe.db.get_value("OAuth Bearer Token", token, "scopes").split(
			get_url_delimiter()
		)
		valid, oauthlib_request = get_oauth_server().verify_request(
			uri, http_method, body, headers, required_scopes
		)
		if valid:
			frappe.set_user(frappe.db.get_value("OAuth Bearer Token", token, "user"))
			frappe.local.form_dict = form_dict
	except AttributeError:
		pass


def validate_auth_via_api_keys(authorization_header):
	"""
	Authenticate request using API keys and set session user

	Args:
	        authorization_header (list of str): The 'Authorization' header containing the prefix and token
	"""

	try:
		auth_type, auth_token = authorization_header
		authorization_source = frappe.get_request_header("Frappe-Authorization-Source")
		if auth_type.lower() == "basic":
			api_key, api_secret = frappe.safe_decode(base64.b64decode(auth_token)).split(":")
			validate_api_key_secret(api_key, api_secret, authorization_source)
		elif auth_type.lower() == "token":
			api_key, api_secret = auth_token.split(":")
			validate_api_key_secret(api_key, api_secret, authorization_source)
	except binascii.Error:
		frappe.throw(
			_("Failed to decode token, please provide a valid base64-encoded token."),
			frappe.InvalidAuthorizationToken,
		)
	except (AttributeError, TypeError, ValueError):
		pass


def validate_api_key_secret(api_key, api_secret, frappe_authorization_source=None):
	"""frappe_authorization_source to provide api key and secret for a doctype apart from User"""
	doctype = frappe_authorization_source or "User"
	docname = frappe.db.get_value(
		doctype=doctype, filters={"api_key": api_key, "enabled": True}, fieldname=["name"]
	)
	if not docname:
		raise frappe.AuthenticationError
	form_dict = frappe.local.form_dict
	doc_secret = get_decrypted_password(doctype, docname, fieldname="api_secret")
	if api_secret == doc_secret:
		if doctype == "User":
			user = frappe.db.get_value(doctype="User", filters={"api_key": api_key}, fieldname=["name"])
		else:
			user = frappe.db.get_value(doctype, docname, "user")
		if frappe.local.login_manager.user in ("", "Guest"):
			frappe.set_user(user)
		frappe.local.form_dict = form_dict
	else:
		raise frappe.AuthenticationError


def validate_auth_via_hooks():
	for auth_hook in frappe.get_hooks("auth_hooks", []):
		frappe.get_attr(auth_hook)()


def check_request_ip():
	if frappe.local.request_ip is None:
		frappe.local.request_ip = "127.0.0.1"
