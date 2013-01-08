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
"""
Boot session from cache or build

Session bootstraps info needed by common client side activities including
permission, homepage, control panel variables, system defaults etc
"""
import webnotes
import conf
import json

@webnotes.whitelist()
def clear(user=None):
	"""clear all cache"""
	clear_cache(user)
	webnotes.response['message'] = "Cache Cleared"

def clear_cache(user=None):
	"""clear cache"""
	webnotes.cache().delete_keys("bootinfo:")
	webnotes.cache().delete_keys("doctype:")
	webnotes.cache().delete_keys("session:")

def clear_sessions(user=None, keep_current=False):
	if not user:
		user = webnotes.session.user
	for sid in webnotes.conn.sql("""select sid from tabSessions where user=%s""", user):
		if not (keep_current and webnotes.session.sid == sid[0]):
			webnotes.cache().delete_value("session:" + sid[0])
	if keep_current:
		webnotes.conn.sql('delete from tabSessions where user=%s and sid!=%s', (user, 
			webnotes.session.sid))
	else:
		webnotes.conn.sql('delete from tabSessions where user=%s', user)
		
def get():
	"""get session boot info"""
	# check if cache exists
	if not getattr(conf,'auto_cache_clear',None):
		cache = webnotes.cache().get_value('bootinfo:' + webnotes.session.user)
		if cache:
			cache['from_cache'] = 1
			return cache
	
	if not webnotes.cache().get_stats():
		webnotes.msgprint("memcached is not working / stopped. Please start memcached for best results.")
	
	# if not create it
	from webnotes.boot import get_bootinfo
	bootinfo = get_bootinfo()
	webnotes.cache().set_value('bootinfo:' + webnotes.session.user, bootinfo)
		
	return bootinfo

class Session:
	def __init__(self, user=None):
		self.user = user
		self.sid = webnotes.form_dict.get('sid') or webnotes.incoming_cookies.get('sid', 'Guest')
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
		if webnotes.login_manager.user=='Guest':
			sid = 'Guest'
		else:
			sid = webnotes.generate_hash()
		
		self.data['user'] = webnotes.login_manager.user
		self.data['sid'] = sid
		self.data['data']['user'] = webnotes.login_manager.user
		self.data['data']['session_ip'] = os.environ.get('REMOTE_ADDR')
		self.data['data']['last_updated'] = webnotes.utils.now()
		self.data['data']['session_expiry'] = self.get_expiry_period()

		# get ipinfo
		if webnotes.conn.get_global('get_ip_info'):
			self.get_ipinfo()
		
		# insert session
		self.insert_session_record()

		# update profile
		webnotes.conn.sql("""UPDATE tabProfile SET last_login = '%s', last_ip = '%s' 
			where name='%s'""" % (webnotes.utils.now(), webnotes.remote_ip, self.data['user']))

		# set cookies to write
		webnotes.session = self.data
		webnotes.cookie_manager.set_cookies()

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
			self.data = webnotes._dict({'data': data, 
				'user':data.user, 'sid': self.sid})
		else:
			self.start_as_guest()

	def get_session_record(self):
		"""get session record, or return the standard Guest Record"""
		# check in memcache
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
		# check if expired
		data = webnotes._(webnotes.cache().get_value("session:" + self.sid))
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
			data = webnotes._dict(eval(rec and rec[0][1] or {}))
			data.user = rec[0][0]
		else:
			self.delete_session()
			data = None

		return data

	def get_expiry_in_seconds(self, expiry):
		if not expiry: return 3600
		parts = expiry.split(":")
		return (int(parts[0] or 0) * 3600) + (int(parts[1] or 0) * 60) + int(parts[2] or 0)

	def delete_session(self):
		webnotes.cache().delete_value("session:" + self.sid)
		r = webnotes.conn.sql("""delete from tabSessions where sid=%s""", self.sid)

	def start_as_guest(self):
		"""all guests share the same 'Guest' session"""
		webnotes.login_manager.login_as_guest()
		self.start()

	def update(self):
		"""extend session expiry"""
		self.data['data']['last_updated'] = webnotes.utils.now()

		# update session in db
		time_diff = None
		last_updated = webnotes.cache().get_value("last_db_session_update:" + self.sid)

		if last_updated:
			time_diff = webnotes.utils.time_diff_in_seconds(webnotes.utils.now(), 
				last_updated)

		if webnotes.session['user'] != 'Guest' and \
			((not time_diff) or (time_diff > 1800)):
			# database persistence is secondary, don't update it too often
			webnotes.conn.sql("""update tabSessions set sessiondata=%s, 
				lastupdate=NOW() where sid=%s""" , (str(self.data['data']), 
				self.data['sid']))
				
			# update timestamp of update
			webnotes.cache().set_value("last_db_session_update:" + self.sid, 
				webnotes.utils.now())

		if webnotes.request.cmd!="webnotes.sessions.clear":
			webnotes.cache().set_value("session:" + self.sid, self.data)

	def get_expiry_period(self):
		exp_sec = webnotes.conn.get_default("session_expiry") or \
			webnotes.conn.get_value('Control Panel', None, 'session_expiry') or '06:00:00'
		
		# incase seconds is missing
		if len(exp_sec.split(':')) == 2:
			exp_sec = exp_sec + ':00'
	
		return exp_sec

	def get_ipinfo(self):
		import os
		
		try:
			import pygeoip
		except:
			return
		
		gi = pygeoip.GeoIP('data/GeoIP.dat')
		self.data['data']['ipinfo'] = {'countryName': gi.country_name_by_addr(os.environ.get('REMOTE_ADDR'))}
		
