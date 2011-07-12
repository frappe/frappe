# Chai Project 0.1
# (c) 2011 Web Notes Technologies
# Chai Project may be freely distributed under MIT license
# Authors: Rushabh Mehta (@rushabh_mehta)
import webnotes.auth
import webnotes
import webnotes.db
import webnotes.utils
import webnotes.profile
import webnotes.defs
class HTTPRequest:
	"""
	Wrapper around HTTPRequest

	- selects database
	- manages session
	- calls "action"

	"""
	def __init__(self):
		self.cmd = None
		self.database = None
		self.set_env_variables()
		self.form = {}		
		self.set_cookies()
		self.connect_db()
		self.check_status()

		##FIXME  : The line below
		webnotes.conn.begin()

		# login
		webnotes.login_manager = webnotes.auth.LoginManager()

		self.load_session()

		# write out cookies if sid is supplied (this is a pre-logged in redirect)
		if self.form.get('sid'):
			webnotes.cookie_manager.set_cookies()

		# run login triggers
		if self.form.get('cmd')=='login':
			webnotes.login_manager.run_trigger('on_login_post_session')
			
		# load profile
		self.setup_profile()

		webnotes.conn.commit()
	
	def setup_profile(self):
		"""
			Setup Profile
		"""
		webnotes.user = webnotes.profile.Profile()
		# load the profile data
		if webnotes.session['data'].get('profile'):
			webnotes.user.load_from_session(webnotes.session['data']['profile'])
		else:
			webnotes.user.load_profile()	

	def get_ac_name(self):
		"""
			try to hunt the account name from various places
		"""
		# login
		if webnotes.form_dict.get('acx'):
			return webnotes.form_dict.get('acx')
		
		# in form
		elif webnotes.request.form.get('ac_name'):
			return webnotes.form_dict.get('ac_name')
			
		# in cookie
		elif webnotes.incoming_cookies.get('ac_name'):
			return webnotes.incoming_cookies.get('ac_name')
			
	def set_cookies(self):
		"""
		Builds cookies dictionary
		"""
		webnotes.cookie_manager = webnotes.auth.CookieManager()
		
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
		webnotes.ac_name = ac_name
		
	def execute(self):
		"""
			Executes the request specified in "action". Action must be a direct
			method call and should be "whitelisted" in the module
		"""
		module = ''
		action = self.form.get('action')
		if '.' in action:
			module = '.'.join(action.split('.')[:-1])
			action = action.split('.')[-1]

			exec 'from %s import %s, whitelist' % (module, cmd) in locals()
			if action in locals().get('whitelist'):
				locals().get(action)()
			else:
				webnotes.msgprint('Unpermitted action')

	def set_env_variables(self):
		"""
			Set environment variables like domain name and ip address
		"""
		self.domain = webnotes.get_env_vars('HTTP_HOST')
		if self.domain and self.domain.startswith('www.'):
			self.domain = self.domain[4:]
		webnotes.remote_ip = webnotes.get_env_vars('REMOTE_ADDR')
	
	def check_status(self):
		"""
			Check session status
		"""
		if webnotes.conn.get_global("__session_status")=='stop':
			webnotes.msgprint(webnotes.conn.get_global("__session_status_message"))
			raise Exception
	def load_session(self):
		"""
			Load the session object
		"""
		webnotes.session_obj = webnotes.auth.Session()
		webnotes.session = webnotes.session_obj.data
		webnotes.tenant_id = webnotes.session.get('tenant_id', 0)
