# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import datetime

from frappe import _
import frappe
import frappe.database
import frappe.utils
import frappe.utils.user
from frappe import conf
from frappe.sessions import Session, clear_sessions, delete_session
from frappe.modules.patch_handler import check_session_stopped

from urllib import quote

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

		self.validate_csrf_token()

		# write out latest cookies
		frappe.local.cookie_manager.init_cookies()

		# check status
		check_session_stopped()

		# run login triggers
		if frappe.form_dict.get('cmd')=='login':
			frappe.local.login_manager.run_trigger('on_session_creation')

	def validate_csrf_token(self):
		if frappe.local.request and frappe.local.request.method=="POST":
			if not frappe.local.session.data.csrf_token or frappe.local.session.data.device=="mobile":
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
		frappe.local.db = frappe.database.Database(user = self.get_db_name(), \
			password = getattr(conf,'db_password', ''))

class LoginManager:
	def __init__(self):
		self.user = None
		self.info = None
		self.full_name = None
		self.user_type = None

		if frappe.local.form_dict.get('cmd')=='login' or frappe.local.request.path=="/api/method/login":
			self.login()
			self.resume = False
		else:
			try:
				self.resume = True
				self.make_session(resume=True)
				self.set_user_info(resume=True)
			except AttributeError:
				self.user = "Guest"
				self.make_session()
				self.set_user_info()

	def login(self):
		# clear cache
		frappe.clear_cache(user = frappe.form_dict.get('usr'))
		self.authenticate()
		self.post_login()

	def post_login(self):
		self.run_trigger('on_login')
		self.validate_ip_address()
		self.validate_hour()
		self.make_session()
		self.set_user_info()

	def set_user_info(self, resume=False):
		# set sid again
		frappe.local.cookie_manager.init_cookies()

		self.info = frappe.db.get_value("User", self.user,
			["user_type", "first_name", "last_name", "user_image"], as_dict=1)
		self.full_name = " ".join(filter(None, [self.info.first_name,
			self.info.last_name]))
		self.user_type = self.info.user_type

		if self.info.user_type=="Website User":
			frappe.local.cookie_manager.set_cookie("system_user", "no")
			if not resume:
				frappe.local.response["message"] = "No App"
		else:
			frappe.local.cookie_manager.set_cookie("system_user", "yes")
			if not resume:
				frappe.local.response['message'] = 'Logged In'

		if not resume:
			frappe.response["full_name"] = self.full_name

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
		if not frappe.conf.get("deny_multiple_sessions"):
			return

		if frappe.session.user != "Guest":
			clear_sessions(frappe.session.user, keep_current=True)

	def authenticate(self, user=None, pwd=None):
		if not (user and pwd):
			user, pwd = frappe.form_dict.get('usr'), frappe.form_dict.get('pwd')
		if not (user and pwd):
			self.fail('Incomplete login details')

		self.check_if_enabled(user)
		self.user = self.check_password(user, pwd)

	def check_if_enabled(self, user):
		"""raise exception if user not enabled"""
		from frappe.utils import cint
		if user=='Administrator': return
		if not cint(frappe.db.get_value('User', user, 'enabled')):
			self.fail('User disabled or missing')

	def check_password(self, user, pwd):
		"""check password"""
		user = frappe.db.sql("""select `user` from __Auth where `user`=%s
			and `password`=password(%s)""", (user, pwd))
		if not user:
			self.fail('Incorrect password')
		else:
			return user[0][0] # in correct case

	def fail(self, message):
		frappe.local.response['message'] = message
		raise frappe.AuthenticationError

	def run_trigger(self, event='on_login'):
		for method in frappe.get_hooks().get(event, []):
			frappe.call(frappe.get_attr(method), login_manager=self)

	def validate_ip_address(self):
		"""check if IP Address is valid"""
		ip_list = frappe.db.get_value('User', self.user, 'restrict_ip', ignore=True)
		if not ip_list:
			return

		ip_list = ip_list.replace(",", "\n").split('\n')
		ip_list = [i.strip() for i in ip_list]

		for ip in ip_list:
			if frappe.local.request_ip.startswith(ip):
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
			delete_session(frappe.session.sid)
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

def _update_password(user, password):
	frappe.db.sql("""insert into __Auth (user, `password`)
		values (%s, password(%s))
		on duplicate key update `password`=password(%s)""", (user,
		password, password))

@frappe.whitelist()
def get_logged_user():
	return frappe.session.user

def clear_cookies():
	if hasattr(frappe.local, "session"):
		frappe.session.sid = ""
	frappe.local.cookie_manager.delete_cookie(["full_name", "user_id", "sid", "user_image", "system_user"])
