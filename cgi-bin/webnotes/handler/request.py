# Chai Project 0.1
# (c) 2011 Web Notes Technologies
# Chai Project may be freely distributed under MIT license
# Authors: Rushabh Mehta (@rushabh_mehta)
import webnotes.handler.session
import webnotes
import webnotes.db
import webnotes.utils
import webnotes.profile
import webnotes.defs
class HTTPRequest:
	"""
	Wrapper around HTTPRequest

	- selects database , Does that mean that it has to connect to it too?
	- manages session
	- calls "cmd"
	"""
	def __getattr__(self,name):
		if name in self.__dict__:
			return self.__dict__[name]
		else:
			return None

	def __init__(self,reqflds):
		self.cmd = None
		self.database = None
		self.set_env_variables()
		#TODO get rid of self.form, the members of form should be memebers of request itself
		self.__dict__.update(reqflds)
		self.connect_db()
		# write out cookies if sid is supplied (this is a pre-logged in redirect)
		# run login triggers
		#if self.form.get('cmd')=='login':
		#	webnotes.login_manager.run_trigger('on_login_post_session')
		webnotes.conn.commit()

	def get_ac_name(self):
		"""
			try to hunt the account name from various places
		"""
		# login
		if hasattr(self,'acx'):
			return self.acx
		
		# in form
		elif hasattr(self,'ac_name'):
			return self.ac_name
			
		# in cookie
		elif webnotes.incoming_cookies.get('ac_name'):
			return webnotes.incoming_cookies.get('ac_name')
		
	def connect_db(self):
		"""
		Selects db
		"""
		# select based on subdomain
		if getattr(webnotes.defs,'domain_name_map', {}).get(self.domain):
			db_name = webnotes.defs.domain_name_map[self.domain]

		# select based on ac_name
		else:
			ac_name = self.get_ac_name()
			if ac_name:
				db_name = getattr(webnotes.defs,'db_name_map',{}).\
					get(ac_name, ac_name)
			else:
				db_name = getattr(webnotes.defs,'default_db_name','')
	
		webnotes.conn = webnotes.db.Database(user = db_name,password = getattr(webnotes.defs,'db_password',''))
		webnotes.ac_name = ac_name #FIXME
		
	def execute(self):
		"""
			Executes the request specified in "cmd". Action must be a direct
			method call and should be "whitelisted" in the module
		"""
		cmd = self.cmd
		try:
			module = ''
			if '.' in cmd:
				module = '.'.join(cmd.split('.')[:-1])
				cmd = cmd.split('.')[-1]
				exec 'from %s import %s' % (module, cmd) in locals()
				ret = locals().get(cmd)()
				return ret

		except webnotes.ValidationError:
			webnotes.conn.rollback()
		except Exception, e:
			webnotes.conn and webnotes.conn.rollback()
			raise Exception, webnotes.utils.getTraceback()
	def set_env_variables(self):
		"""
			Set environment variables like domain name and ip address
		"""
		self.domain = webnotes.get_env_vars('HTTP_HOST')
		if self.domain and self.domain.startswith('www.'):
			self.domain = self.domain[4:]
		webnotes.remote_ip = webnotes.get_env_vars('REMOTE_ADDR')
