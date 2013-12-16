# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
"""
Boot session from cache or build

Session bootstraps info needed by common client side activities including
permission, homepage, control panel variables, system defaults etc
"""
import webnotes
import json
from webnotes.utils import cint
import webnotes.model.doctype
import webnotes.defaults

@webnotes.whitelist()
def clear(user=None):
	clear_cache(webnotes.session.user)
	webnotes.response['message'] = "Cache Cleared"


def clear_cache(user=None):
	cache = webnotes.cache()

	cache.delete_value(["app_hooks", "installed_apps", "app_modules", "module_apps"])

	# clear doctype cache
	webnotes.model.doctype.clear_cache()
	
	if user:
		cache.delete_value("bootinfo:" + user)
		
		# clear notifications
		webnotes.conn.sql("""delete from `tabNotification Count` where owner=%s""", user)
		
		if webnotes.session:
			if user==webnotes.session.user and webnotes.session.sid:
				cache.delete_value("session:" + webnotes.session.sid)
			else:
				for sid in webnotes.conn.sql_list("""select sid from tabSessions
					where user=%s""", user):
						cache.delete_value("session:" + sid)
	else:
		for sess in webnotes.conn.sql("""select user, sid from tabSessions""", as_dict=1):
			cache.delete_value("sesssion:" + sess.sid)
			cache.delete_value("bootinfo:" + sess.user)

def clear_sessions(user=None, keep_current=False):
	if not user:
		user = webnotes.session.user
	for sid in webnotes.conn.sql("""select sid from tabSessions where user=%s""", user):
		if keep_current and webnotes.session.sid==sid[0]:
			pass
		else:
			webnotes.cache().delete_value("session:" + sid[0])
			webnotes.conn.sql("""delete from tabSessions where sid=%s""", sid[0])

def get():
	"""get session boot info"""
	from webnotes.core.doctype.notification_count.notification_count import \
		get_notification_info_for_boot, get_notifications
	
	bootinfo = None
	if not getattr(webnotes.conf,'disable_session_cache',None):
		# check if cache exists
		bootinfo = webnotes.cache().get_value('bootinfo:' + webnotes.session.user)
		if bootinfo:
			bootinfo['from_cache'] = 1
			bootinfo["notification_info"].update(get_notifications())
		
	if not bootinfo:
		if not webnotes.cache().get_stats():
			webnotes.msgprint("memcached is not working / stopped. Please start memcached for best results.")
	
		# if not create it
		from webnotes.boot import get_bootinfo
		bootinfo = get_bootinfo()
		bootinfo["notification_info"] = get_notification_info_for_boot()
		webnotes.cache().set_value('bootinfo:' + webnotes.session.user, bootinfo)
	
	return bootinfo

class Session:
	def __init__(self, user=None):
		self.user = user
		self.sid = webnotes.form_dict.get('sid') or webnotes.request.cookies.get('sid', 'Guest')
		self.data = webnotes._dict({'user':user,'data': webnotes._dict({})})
		self.time_diff = None

		if webnotes.form_dict.get('cmd')=='login':
			self.start()
			return
			
		self.load()

	def start(self):
		"""start a new session"""
		import os
		import webnotes
		import webnotes.utils
		
		# generate sid
		if webnotes.local.login_manager.user=='Guest':
			sid = 'Guest'
		else:
			sid = webnotes.generate_hash()
		
		self.data['user'] = webnotes.local.login_manager.user
		self.data['sid'] = sid
		self.data['data']['user'] = webnotes.local.login_manager.user
		self.data['data']['session_ip'] = webnotes.get_request_header('REMOTE_ADDR')
		self.data['data']['last_updated'] = webnotes.utils.now()
		self.data['data']['session_expiry'] = self.get_expiry_period()
		self.data['data']['session_country'] = get_geo_ip_country(webnotes.get_request_header('REMOTE_ADDR'))
		
		# insert session
		webnotes.conn.begin()
		self.insert_session_record()

		# update profile
		webnotes.conn.sql("""UPDATE tabProfile SET last_login = '%s', last_ip = '%s' 
			where name='%s'""" % (webnotes.utils.now(), webnotes.get_request_header('REMOTE_ADDR'), self.data['user']))
		webnotes.conn.commit()
		
		# set cookies to write
		webnotes.local.session = self.data

	def insert_session_record(self):
		webnotes.conn.sql("""insert into tabSessions 
			(sessiondata, user, lastupdate, sid, status) 
			values (%s , %s, NOW(), %s, 'Active')""", 
				(str(self.data['data']), self.data['user'], self.data['sid']))
				
		# also add to memcache
		webnotes.cache().set_value("session:" + self.data.sid, self.data)

	def load(self):
		"""non-login request: load a session"""
		import webnotes		
		data = self.get_session_record()
		if data:
			# set language
			if data.lang and self.user!="demo@erpnext.com": 
				webnotes.local.lang = data.lang
			self.data = webnotes._dict({'data': data, 
				'user':data.user, 'sid': self.sid})
		else:
			self.start_as_guest()

	def get_session_record(self):
		"""get session record, or return the standard Guest Record"""
		r = self.get_session_data()
		if not r:
			webnotes.response["session_expired"] = 1
			self.sid = "Guest"
			r = self.get_session_data()
			
		return r

	def get_session_data(self):
		data = self.get_session_data_from_cache()
		if not data:
			data = self.get_session_data_from_db()
		return data

	def get_session_data_from_cache(self):
		data = webnotes._dict(webnotes.cache().get_value("session:" + self.sid) or {})
		if data:
			session_data = data.get("data", {})
			self.time_diff = webnotes.utils.time_diff_in_seconds(webnotes.utils.now(), 
				session_data.get("last_updated"))
			expiry = self.get_expiry_in_seconds(session_data.get("session_expiry"))

			if self.time_diff > expiry:
				self.delete_session()
				data = None
				
		return data and data.data

	def get_session_data_from_db(self):
		if self.sid=="Guest":
			rec = webnotes.conn.sql("""select user, sessiondata from 
				tabSessions where sid='Guest' """)
		else:
			rec = webnotes.conn.sql("""select user, sessiondata 
				from tabSessions where sid=%s and 
				TIMEDIFF(NOW(), lastupdate) < TIME(%s)""", (self.sid, 
					self.get_expiry_period()))
		if rec:
			data = webnotes._dict(eval(rec and rec[0][1] or '{}'))
			data.user = rec[0][0]
		else:
			self.delete_session()
			data = None

		return data

	def get_expiry_in_seconds(self, expiry):
		if not expiry: return 3600
		parts = expiry.split(":")
		return (cint(parts[0]) * 3600) + (cint(parts[1]) * 60) + cint(parts[2])

	def delete_session(self):
		webnotes.cache().delete_value("session:" + self.sid)
		r = webnotes.conn.sql("""delete from tabSessions where sid=%s""", self.sid)

	def start_as_guest(self):
		"""all guests share the same 'Guest' session"""
		webnotes.local.login_manager.login_as_guest()
		self.start()

	def update(self):
		"""extend session expiry"""
		self.data['data']['last_updated'] = webnotes.utils.now()
		self.data['data']['lang'] = unicode(webnotes.lang)


		# update session in db
		time_diff = None
		last_updated = webnotes.cache().get_value("last_db_session_update:" + self.sid)

		if last_updated:
			time_diff = webnotes.utils.time_diff_in_seconds(webnotes.utils.now(), 
				last_updated)
		
		if webnotes.session['user'] != 'Guest' and \
			((time_diff==None) or (time_diff > 1800)):
			# database persistence is secondary, don't update it too often
			webnotes.conn.sql("""update tabSessions set sessiondata=%s, 
				lastupdate=NOW() where sid=%s""" , (str(self.data['data']), 
				self.data['sid']))

		if webnotes.form_dict.cmd not in ("webnotes.sessions.clear", "logout"):
			webnotes.cache().set_value("last_db_session_update:" + self.sid, 
				webnotes.utils.now())
			webnotes.cache().set_value("session:" + self.sid, self.data)

	def get_expiry_period(self):
		exp_sec = webnotes.defaults.get_global_default("session_expiry") or "06:00:00"
		
		# incase seconds is missing
		if exp_sec:
			if len(exp_sec.split(':')) == 2:
				exp_sec = exp_sec + ':00'
		else:
			exp_sec = "2:00:00"
	
		return exp_sec
		
def get_geo_ip_country(ip_addr):
	try:
		import pygeoip
	except ImportError:
		return
	
	import os
	from webnotes.utils import get_base_path

	try:
		geo_ip_file = os.path.join(get_base_path(), "lib", "data", "GeoIP.dat")
		geo_ip = pygeoip.GeoIP(geo_ip_file, pygeoip.MEMORY_CACHE)
		return geo_ip.country_name_by_addr(ip_addr)
	except Exception, e:
		return

