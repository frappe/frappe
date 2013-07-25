# Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
# 
# MIT License (MIT)
# 
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# 

from __future__ import unicode_literals
import webnotes
import webnotes.db
import webnotes.utils
import webnotes.profile
import conf
from webnotes.sessions import Session


class HTTPRequest:
	def __init__(self):

		# Get Environment variables
		self.domain = webnotes.get_env_vars('HTTP_HOST')
		if self.domain and self.domain.startswith('www.'):
			self.domain = self.domain[4:]

		# language
		self.set_lang(webnotes.get_env_vars('HTTP_ACCEPT_LANGUAGE'))
		
		webnotes.remote_ip = webnotes.get_env_vars('REMOTE_ADDR')

		# load cookies
		webnotes.cookie_manager = CookieManager()

		webnotes.request_method = webnotes.get_env_vars("REQUEST_METHOD")
		
		# override request method. All request to be of type POST, but if _type == "POST" then commit
		if webnotes.form_dict.get("_type"):
			webnotes.request_method = webnotes.form_dict.get("_type")
			del webnotes.form_dict["_type"]

		# set db
		self.connect()

		# login
		webnotes.login_manager = LoginManager()

		# start session
		webnotes.session_obj = Session()
		webnotes.session = webnotes.session_obj.data

		# check status
		if webnotes.conn.get_global("__session_status")=='stop':
			webnotes.msgprint(webnotes.conn.get_global("__session_status_message"))
			raise webnotes.SessionStopped('Session Stopped')

		# load profile
		self.setup_profile()

		# run login triggers
		if webnotes.form_dict.get('cmd')=='login':
			webnotes.login_manager.run_trigger('on_login_post_session')

		# write out cookies
		webnotes.cookie_manager.set_cookies()

	def set_lang(self, lang):
		try:
			from startup import lang_list
		except ImportError, e:
			return
		
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
				webnotes.lang = code
				return
				
			# check if parent language (pt) is setup, if variant (pt-BR)
			if "-" in code:
				code = code.split("-")[0]
				if code in lang_list:
					webnotes.lang = code
					return

	def setup_profile(self):
		webnotes.user = webnotes.profile.Profile()

	def get_db_name(self):
		"""get database name from conf"""
		return conf.db_name

	def connect(self, ac_name = None):
		"""connect to db, from ac_name or db_name"""
		webnotes.conn = webnotes.db.Database(user = self.get_db_name(), \
			password = getattr(conf,'db_password', ''))

class LoginManager:
	def __init__(self):
		if webnotes.form_dict.get('cmd')=='login':
			# clear cache
			from webnotes.sessions import clear_cache
			clear_cache(webnotes.form_dict.get('usr'))

			self.authenticate()
			self.post_login()
			info = webnotes.conn.get_value("Profile", self.user, ["user_type", "first_name", "last_name"], as_dict=1)
			if info.user_type=="Website User":
				webnotes.response["message"] = "No App"
				full_name = " ".join(filter(None, [info.first_name, info.last_name]))
				webnotes.response["full_name"] = full_name
				webnotes.add_cookies["full_name"] = full_name
			else:
				webnotes.response['message'] = 'Logged In'
	
	def post_login(self):
		self.run_trigger()
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
		try:
			from startup import event_handlers
			if hasattr(event_handlers, method):
				getattr(event_handlers, method)(self)
			return
		except ImportError, e:
			pass
	
	def validate_ip_address(self):
		"""check if IP Address is valid"""
		ip_list = webnotes.conn.get_value('Profile', self.user, 'restrict_ip', ignore=True)
		
		if not ip_list:
			return

		ip_list = ip_list.replace(",", "\n").split('\n')
		ip_list = [i.strip() for i in ip_list]

		for ip in ip_list:
			if webnotes.remote_ip.startswith(ip):
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
			webnotes.add_cookies["full_name"] = ""
			webnotes.add_cookies["sid"] = ""
		
class CookieManager:
	def __init__(self):
		import Cookie
		webnotes.cookies = Cookie.SimpleCookie()
		self.get_incoming_cookies()

	def get_incoming_cookies(self):
		import os
		cookies = {}
		if 'HTTP_COOKIE' in os.environ:
			c = os.environ['HTTP_COOKIE']
			webnotes.cookies.load(c)
			for c in webnotes.cookies.values():
				cookies[c.key] = c.value
					
		webnotes.incoming_cookies = cookies
		
	def set_cookies(self):		
		if not webnotes.session.get('sid'): return		
		import datetime

		# sid expires in 3 days
		expires = datetime.datetime.now() + datetime.timedelta(days=3)
		expires = expires.strftime('%a, %d %b %Y %H:%M:%S')
		
		webnotes.cookies[b'sid'] = webnotes.session['sid'].encode('utf-8')
		webnotes.cookies[b'sid'][b'expires'] = expires.encode('utf-8')
		
		webnotes.cookies[b'country'] = webnotes.session.get("session_country")
		
	def set_remember_me(self):
		from webnotes.utils import cint
		
		if not cint(webnotes.form_dict.get('remember_me')): return
		
		remember_days = webnotes.conn.get_value('Control Panel', None,
			'remember_for_days') or 7
			
		import datetime
		expires = datetime.datetime.now() + \
					datetime.timedelta(days=remember_days)
		expires = expires.strftime('%a, %d %b %Y %H:%M:%S')

		webnotes.cookies[b'remember_me'] = 1
		for k in webnotes.cookies.keys():
			webnotes.cookies[k][b'expires'] = expires.encode('utf-8')


def update_password(user, password):
	webnotes.conn.sql("""insert into __Auth (user, `password`) 
		values (%s, password(%s)) 
		on duplicate key update `password`=password(%s)""", (user, 
		password, password))
	