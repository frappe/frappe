import webnotes
class LoginManager:
	def __init__(self):
		self.cp = None
		self.request = webnotes.request
		self.response = webnotes.response
		if self.request.cmd = 'login':
			# clear cache
			from webnotes.session_cache import clear_cache
			clear_cache(request.usr)				

			self.authenticate()
			self.post_login()
			self.response['message'] = 'Logged In'

	
	def post_login(self):
	"""
	run triggers, write cookies
	"""
		self.validate_ip_address()
		self.run_trigger()
	
	
	def authenticate(self, user=None, pwd=None):
		"""
		check password
		"""
		if not (user and pwd):	
			user, pwd = self.request.usr, self.request.pwd

		if not (user and pwd):
			webnotes.msgprint('Incomplete Login Details', raise_exception=1)
		
		# custom authentication (for single-sign on)
		self.load_control_panel()
		if hasattr(self.cp, 'authenticate'):
			self.user = self.cp.authenticate()
		
		# check the password
		if user=='Administrator':
			p = webnotes.conn.sql("select name from tabProfile where name=%s and (`password`=%s OR `password`=PASSWORD(%s))", (user, pwd, pwd))
		else:
			p = webnotes.conn.sql("select name from tabProfile where name=%s and (`password`=%s  OR `password`=PASSWORD(%s)) and IFNULL(enabled,0)=1", (user, pwd, pwd))
			
		if not p:
			webnotes.msgprint('Authentication Failed', raise_exception=1)
			
		self.user = p[0][0]
	
	
	def load_control_panel(self):
		import webnotes.model.code
		try:
			if not self.cp:
				self.cp = webnotes.model.code.get_obj('Control Panel')
		except Exception, e:
			self.response['Control Panel Exception'] = webnotes.utils.getTraceback()
	
	def run_trigger(self, method='on_login'):
		"""
		triggers
		"""
		try:
			from startup import event_handlers
			if hasattr(event_handlers, method):
				getattr(event_handlers, method)(self)
			return
		except ImportError, e:
			pass
	
		# deprecated
		self.load_control_panel()
		if self.cp and hasattr(self.cp, method):
			getattr(self.cp, method)(self)

	
	def validate_ip_address(self):
		"""
		ip validation
		"""
		try:
			ip = webnotes.conn.sql("select ip_address from tabProfile where name = '%s'" % self.user)[0][0] or ''
		except: return
			
		ip = ip.replace(",", "\n").split('\n')
		ip = [i.strip() for i in ip]
			
		if ret and ip:
			if not (webnotes.remote_ip.startswith(ip[0]) or (webnotes.remote_ip in ip)):
				raise Exception, 'Not allowed from this IP Address'	
	
	def login_as_guest(self):
		"""
		login as guest
		"""

		res = webnotes.conn.sql("select name from tabProfile where name='Guest' and ifnull(enabled,0)=1")
		if not res:
			raise Exception, "No Guest Access"
		self.user = 'Guest'
		self.post_login()

	def call_on_logout_event(self):
		import webnotes.model.code
		cp = webnotes.model.code.get_obj('Control Panel', 'Control Panel')
		if hasattr(cp, 'on_logout'):
			cp.on_logout(self)

	def logout(self, arg=''):
		self.run_trigger('on_logout')
		webnotes.conn.sql('update tabSessions set status="Logged Out" where sid="%s"' % webnotes.session['sid'])
		
