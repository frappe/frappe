# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import webnotes
import webnotes.db
import webnotes.utils
import webnotes.profile
from webnotes import conf
from webnotes.sessions import Session


class HTTPRequest:
	def __init__(self):
		# Get Environment variables
		self.domain = webnotes.request.host
		if self.domain and self.domain.startswith('www.'):
			self.domain = self.domain[4:]

		# language
		self.set_lang(webnotes.get_request_header('HTTP_ACCEPT_LANGUAGE'))
		
		# load cookies
		webnotes.local.cookie_manager = CookieManager()
		
		# override request method. All request to be of type POST, but if _type == "POST" then commit
		if webnotes.form_dict.get("_type"):
			webnotes.local.request_method = webnotes.form_dict.get("_type")
			del webnotes.form_dict["_type"]

		# set db
		self.connect()

		# login
		webnotes.local.login_manager = LoginManager()

		# start session
		webnotes.local.session_obj = Session()
		webnotes.local.session = webnotes.local.session_obj.data

		# check status
		if webnotes.conn.get_global("__session_status")=='stop':
			webnotes.msgprint(webnotes.conn.get_global("__session_status_message"))
			raise webnotes.SessionStopped('Session Stopped')

		# load profile
		self.setup_profile()

		# run login triggers
		if webnotes.form_dict.get('cmd')=='login':
			webnotes.local.login_manager.run_trigger('on_session_creation')

		# write out cookies
		webnotes.local.cookie_manager.set_cookies()

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
				webnotes.local.lang = code
				return
				
			# check if parent language (pt) is setup, if variant (pt-BR)
			if "-" in code:
				code = code.split("-")[0]
				if code in lang_list:
					webnotes.local.lang = code
					return
					
	def setup_profile(self):
		webnotes.local.user = webnotes.profile.Profile()

	def get_db_name(self):
		"""get database name from conf"""
		return conf.db_name

	def connect(self, ac_name = None):
		"""connect to db, from ac_name or db_name"""
		webnotes.local.conn = webnotes.db.Database(user = self.get_db_name(), \
			password = getattr(conf,'db_password', ''))

class LoginManager:
	def __init__(self):
		if webnotes.form_dict.get('cmd')=='login':
			# clear cache
			webnotes.clear_cache(user = webnotes.form_dict.get('usr'))

			self.authenticate()
			self.post_login()
			info = webnotes.conn.get_value("Profile", self.user, ["user_type", "first_name", "last_name"], as_dict=1)
			if info.user_type=="Website User":
				webnotes._response.set_cookie("system_user", "no")
				webnotes.response["message"] = "No App"
			else:
				webnotes._response.set_cookie("system_user", "yes")
				webnotes.response['message'] = 'Logged In'

			full_name = " ".join(filter(None, [info.first_name, info.last_name]))
			webnotes.response["full_name"] = full_name
			webnotes._response.set_cookie("full_name", full_name)
			webnotes._response.set_cookie("user_id", self.user)

	def post_login(self):
		self.run_trigger('on_login')
		self.validate_ip_address()
		self.validate_hour()
	
	def authenticate(self, user=None, pwd=None):
		if not (user and pwd):	
			user, pwd = webnotes.form_dict.get('usr'), webnotes.form_dict.get('pwd')
		if not (user and pwd):
			self.fail('Incomplete login details')
		
		self.check_if_enabled(user)
		self.user = self.check_password(user, pwd)
	
	def check_if_enabled(self, user):
		"""raise exception if user not enabled"""
		from webnotes.utils import cint
		if user=='Administrator': return
		if not cint(webnotes.conn.get_value('Profile', user, 'enabled')):
			self.fail('User disabled or missing')

	def check_password(self, user, pwd):
		"""check password"""
		user = webnotes.conn.sql("""select `user` from __Auth where `user`=%s 
			and `password`=password(%s)""", (user, pwd))
		if not user:
			self.fail('Incorrect password')
		else:
			return user[0][0] # in correct case
	
	def fail(self, message):
		webnotes.response['message'] = message
		raise webnotes.AuthenticationError
		
	
	def run_trigger(self, method='on_login'):
		for method in webnotes.get_hooks().get("method", []):
			webnotes.get_attr(method)(self)
	
	def validate_ip_address(self):
		"""check if IP Address is valid"""
		ip_list = webnotes.conn.get_value('Profile', self.user, 'restrict_ip', ignore=True)
		
		if not ip_list:
			return

		ip_list = ip_list.replace(",", "\n").split('\n')
		ip_list = [i.strip() for i in ip_list]

		for ip in ip_list:
			if webnotes.get_request_header('REMOTE_ADDR', '').startswith(ip) or webnotes.get_request_header('X-Forwarded-For', '').startswith(ip):
				return
			
		webnotes.msgprint('Not allowed from this IP Address')
		raise webnotes.AuthenticationError

	def validate_hour(self):
		"""check if user is logging in during restricted hours"""
		login_before = int(webnotes.conn.get_value('Profile', self.user, 'login_before', ignore=True) or 0)
		login_after = int(webnotes.conn.get_value('Profile', self.user, 'login_after', ignore=True) or 0)
		
		if not (login_before or login_after):
			return
			
		from webnotes.utils import now_datetime
		current_hour = int(now_datetime().strftime('%H'))
				
		if login_before and current_hour > login_before:
			webnotes.msgprint('Not allowed to login after restricted hour', raise_exception=1)

		if login_after and current_hour < login_after:
			webnotes.msgprint('Not allowed to login before restricted hour', raise_exception=1)
	
	def login_as_guest(self):
		"""login as guest"""
		self.user = 'Guest'
		self.post_login()

	def logout(self, arg='', user=None):
		if not user: user = webnotes.session.user
		self.run_trigger('on_logout')
		if user in ['demo@erpnext.com', 'Administrator']:
			webnotes.conn.sql('delete from tabSessions where sid=%s', webnotes.session.get('sid'))
			webnotes.cache().delete_value("session:" + webnotes.session.get("sid"))
		else:
			from webnotes.sessions import clear_sessions
			clear_sessions(user)

		if user == webnotes.session.user:
			webnotes.session.sid = ""
			webnotes._response.delete_cookie("full_name")
			webnotes._response.delete_cookie("user_id")
			webnotes._response.delete_cookie("sid")
			webnotes._response.set_cookie("full_name", "")
			webnotes._response.set_cookie("user_id", "")
			webnotes._response.set_cookie("sid", "")

class CookieManager:
	def __init__(self):
		pass
		
	def set_cookies(self):
		if not webnotes.session.get('sid'): return		
		import datetime

		# sid expires in 3 days
		expires = datetime.datetime.now() + datetime.timedelta(days=3)
		if webnotes.session.sid:
			webnotes._response.set_cookie("sid", webnotes.session.sid, expires = expires)
		if webnotes.session.session_country:
			webnotes._response.set_cookie('country', webnotes.session.get("session_country"))
		
	def set_remember_me(self):
		from webnotes.utils import cint
		
		if not cint(webnotes.form_dict.get('remember_me')): return
		
		remember_days = webnotes.conn.get_value('Control Panel', None,
			'remember_for_days') or 7
			
		import datetime
		expires = datetime.datetime.now() + \
					datetime.timedelta(days=remember_days)

		webnotes._response.set_cookie["remember_me"] = 1


def _update_password(user, password):
	webnotes.conn.sql("""insert into __Auth (user, `password`) 
		values (%s, password(%s)) 
		on duplicate key update `password`=password(%s)""", (user, 
		password, password))
	
@webnotes.whitelist()
def get_logged_user():
	return webnotes.session.user
