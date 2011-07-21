import webnotes
import webnotes.db
import webnotes.utils
import webnotes.profile
import webnotes.defs
#TODO Put Docsrtings here
class Session:
	def __init__(self, user=None):
		self.user = user
		self.request = webnotes.request
		self.sid = self.request.sid or webnotes.incoming_cookies.get('sid')
		self.data = {'user':user,'data':{}}
		
		if self.request.cmd=='login':
			self.start()
			return
			
		self.load()
	
	# start a session
	# ---------------
	def load(self):
		import webnotes
		
		r=None
		try:
			r = webnotes.conn.sql("select user, sessiondata, status from tabSessions where sid='%s'" % self.sid)
		except Exception, e:
			if e.args[0]==1054:
				self.add_status_column()
			else:
				raise e
	
		if r:
			r=r[0]
			
			# ExipredSession
			if r[2]=='Expired' and (self.request.cmd=='resume_session'):
				if r[0]=='Guest' or (not self.request.cmd or self.request.cmd=='logout'):
					webnotes.login_manager.login_as_guest()
					self.start()
				else:
					webnotes.response['session_status'] = 'Session Expired'
					raise Exception, 'Session Expired'
			elif r[2]=='Logged Out':
				webnotes.login_manager.login_as_guest()
				self.start()
				# allow refresh or logout
				if self.request.cmd and self.request.cmd!='logout':
					webnotes.response['session_status'] = 'Logged Out'
					raise Exception, 'Logged Out'
			else:
				self.data = {'data':eval(r[1]), 'user':r[0], 'sid': self.sid}
		else:				
			webnotes.login_manager.login_as_guest()
			self.start()
			

	# start a session
	# ---------------
	def start(self):
		import os
		import webnotes
		import webnotes.utils
		
		# generate sid
		self.data['user'] = webnotes.login_manager.user
		self.data['sid'] = webnotes.utils.generate_hash()
		self.data['data']['session_ip'] = os.environ.get('REMOTE_ADDR');
		self.data['data']['tenant_id'] = self.request.tenant_id

		# get ipinfo
		if webnotes.conn.get_global('get_ip_info'):
			self.get_ipinfo()
		
		# insert session
		try:
			self.insert_session_record()
		except Exception, e:
			if e.args[0]==1054:
				self.add_status_column()
				self.insert_session_record()
			else:
				raise e

		# update profile
		webnotes.conn.sql("UPDATE tabProfile SET last_login = '%s', last_ip = '%s' where name='%s'" % (webnotes.utils.now(), webnotes.remote_ip, self.data['user']))

		# set cookies to write
		webnotes.session = self.data
		webnotes.cookie_manager.set_cookies()


	# resume session
	# --------------
	def resume(self):
		pwd = self.request.pwd
		webnotes.login_manager.authenticate(self.data['user'], pwd)
		webnotes.conn.sql("update tabSessions set status='Active' where sid=%s", self.data['sid'])
		return 'Logged In'
	
	# update session
	# --------------
	def update(self):
		# update session
		webnotes.conn.sql("update tabSessions set sessiondata=%s, user=%s, lastupdate=NOW() where sid=%s" , (str(self.data['data']), self.data['user'], self.data['sid']))	

		self.check_expired()

	# check expired
	# -------------
	def check_expired(self):
		# in control panel?
		exp_sec = webnotes.conn.get_value('Control Panel', None, 'session_expiry') or '6:00:00'
		
		# set sessions as expired
		try:
			webnotes.conn.sql("update from tabSessions where TIMEDIFF(NOW(), lastupdate) > %s SET `status`='Expired'", exp_sec)
		except Exception, e:
			if e.args[0]==1054:
				self.add_status_column()
		
		# clear out old sessions
		webnotes.conn.sql("delete from tabSessions where TIMEDIFF(NOW(), lastupdate) > '72:00:00'")

	# -----------------------------
	def add_status_column(self):
		webnotes.conn.commit()
		webnotes.conn.sql("alter table tabSessions add column `status` varchar(20)")
		webnotes.conn.begin()


	# Get IP Info from ipinfodb.com
	# -----------------------------
	def get_ipinfo(self):
		import os
		
		try:
			import pygeoip
		except:
			return
		
		gi = pygeoip.GeoIP('data/GeoIP.dat')
		self.data['data']['ipinfo'] = {'countryName': gi.country_name_by_addr(os.environ.get('REMOTE_ADDR'))}
			
	# -----------------------------
	def insert_session_record(self):
		webnotes.conn.sql("insert into tabSessions (sessiondata, user, lastupdate, sid, status) values (%s , %s, NOW(), %s, 'Active')", (str(self.data['data']), self.data['user'], self.data['sid']))
		
