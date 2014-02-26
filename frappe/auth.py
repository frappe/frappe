# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import frappe
import frappe.database
import frappe.utils
import frappe.profile
from frappe import conf
from frappe.sessions import Session


class HTTPRequest:
	def __init__(self):
		# Get Environment variables
		self.domain = frappe.request.host
		if self.domain and self.domain.startswith('www.'):
			self.domain = self.domain[4:]

		# language
		self.set_lang(frappe.get_request_header('HTTP_ACCEPT_LANGUAGE'))
		
		# load cookies
		frappe.local.cookie_manager = CookieManager()
		
		# override request method. All request to be of type POST, but if _type == "POST" then commit
		if frappe.form_dict.get("_type"):
			frappe.local.request_method = frappe.form_dict.get("_type")
			del frappe.form_dict["_type"]

		# set db
		self.connect()

		# login
		frappe.local.login_manager = LoginManager()

		# check status
		if frappe.db.get_global("__session_status")=='stop':
			frappe.msgprint(frappe.db.get_global("__session_status_message"))
			raise frappe.SessionStopped('Session Stopped')

		# load profile
		self.setup_profile()

		# run login triggers
		if frappe.form_dict.get('cmd')=='login':
			frappe.local.login_manager.run_trigger('on_session_creation')

	def set_lang(self, lang):
		import translate
		lang_list = translate.get_all_languages() or []

		if not lang: 
			return
		if ";" in lang: # not considering weightage
			lang = lang.split(";")[0]
		if "," in lang:
			lang = lang.split(",")
		else:
			lang = [lang]
			
		for l in lang:
			code = l.strip()
			if code in lang_list:
				frappe.local.lang = code
				return
				
			# check if parent language (pt) is setup, if variant (pt-BR)
			if "-" in code:
				code = code.split("-")[0]
				if code in lang_list:
					frappe.local.lang = code
					return
					
	def setup_profile(self):
		frappe.local.user = frappe.profile.Profile()

	def get_db_name(self):
		"""get database name from conf"""
		return conf.db_name

	def connect(self, ac_name = None):
		"""connect to db, from ac_name or db_name"""
		frappe.local.db = frappe.db.Database(user = self.get_db_name(), \
			password = getattr(conf,'db_password', ''))

class LoginManager:
	def __init__(self):
		self.user = None
		if frappe.local.form_dict.get('cmd')=='login' or frappe.local.request.path=="/api/method/login":
			self.login()
		else:
			self.make_session(resume=True)

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
	
	def set_user_info(self):
		info = frappe.db.get_value("Profile", self.user, 
			["user_type", "first_name", "last_name", "user_image"], as_dict=1)
		if info.user_type=="Website User":
			frappe.local._response.set_cookie("system_user", "no")
			frappe.local.response["message"] = "No App"
		else:
			frappe.local._response.set_cookie("system_user", "yes")
			frappe.local.response['message'] = 'Logged In'

		full_name = " ".join(filter(None, [info.first_name, info.last_name]))
		frappe.response["full_name"] = full_name
		frappe._response.set_cookie("full_name", full_name)
		frappe._response.set_cookie("user_id", self.user)
		frappe._response.set_cookie("user_image", info.user_image or "")
		
	def make_session(self, resume=False):
		# start session
		frappe.local.session_obj = Session(user=self.user, resume=resume)
		
		# reset user if changed to Guest
		self.user = frappe.local.session_obj.user
		frappe.local.session = frappe.local.session_obj.data
	
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
		if not cint(frappe.db.get_value('Profile', user, 'enabled')):
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
		
	
	def run_trigger(self, method='on_login'):
		for method in frappe.get_hooks().get("method", []):
			frappe.get_attr(method)(self)
	
	def validate_ip_address(self):
		"""check if IP Address is valid"""
		ip_list = frappe.db.get_value('Profile', self.user, 'restrict_ip', ignore=True)
		
		if not ip_list:
			return

		ip_list = ip_list.replace(",", "\n").split('\n')
		ip_list = [i.strip() for i in ip_list]

		for ip in ip_list:
			if frappe.get_request_header('REMOTE_ADDR', '').startswith(ip) or frappe.get_request_header('X-Forwarded-For', '').startswith(ip):
				return
			
		frappe.msgprint('Not allowed from this IP Address')
		raise frappe.AuthenticationError

	def validate_hour(self):
		"""check if user is logging in during restricted hours"""
		login_before = int(frappe.db.get_value('Profile', self.user, 'login_before', ignore=True) or 0)
		login_after = int(frappe.db.get_value('Profile', self.user, 'login_after', ignore=True) or 0)
		
		if not (login_before or login_after):
			return
			
		from frappe.utils import now_datetime
		current_hour = int(now_datetime().strftime('%H'))
				
		if login_before and current_hour > login_before:
			frappe.msgprint('Not allowed to login after restricted hour', raise_exception=1)

		if login_after and current_hour < login_after:
			frappe.msgprint('Not allowed to login before restricted hour', raise_exception=1)
	
	def login_as_guest(self):
		"""login as guest"""
		self.user = 'Guest'
		self.post_login()

	def logout(self, arg='', user=None):
		if not user: user = frappe.session.user
		self.run_trigger('on_logout')
		if user in ['demo@erpnext.com', 'Administrator']:
			frappe.db.sql('delete from tabSessions where sid=%s', frappe.session.get('sid'))
			frappe.cache().delete_value("session:" + frappe.session.get("sid"))
		else:
			from frappe.sessions import clear_sessions
			clear_sessions(user)

		if user == frappe.session.user:
			frappe.session.sid = ""
			frappe.local._response.delete_cookie("full_name")
			frappe.local._response.delete_cookie("user_id")
			frappe.local._response.delete_cookie("sid")
			frappe.local._response.set_cookie("full_name", "")
			frappe.local._response.set_cookie("user_id", "")
			frappe.local._response.set_cookie("sid", "")

class CookieManager:
	def __init__(self):
		pass
		
	def set_cookies(self):
		if not frappe.local.session.get('sid'): return		
		import datetime

		# sid expires in 3 days
		expires = datetime.datetime.now() + datetime.timedelta(days=3)
		if frappe.session.sid:
			frappe.local._response.set_cookie("sid", frappe.session.sid, expires = expires)
		if frappe.session.session_country:
			frappe.local._response.set_cookie('country', frappe.session.get("session_country"))
		
	def set_remember_me(self):
		from frappe.utils import cint
		
		if not cint(frappe.form_dict.get('remember_me')): return
		
		remember_days = frappe.db.get_value('Control Panel', None,
			'remember_for_days') or 7
			
		import datetime
		expires = datetime.datetime.now() + \
					datetime.timedelta(days=remember_days)

		frappe.local._response.set_cookie["remember_me"] = 1


def _update_password(user, password):
	frappe.db.sql("""insert into __Auth (user, `password`) 
		values (%s, password(%s)) 
		on duplicate key update `password`=password(%s)""", (user, 
		password, password))
	
@frappe.whitelist()
def get_logged_user():
	return frappe.session.user
