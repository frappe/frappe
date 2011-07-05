# Chai Project 0.1
# (c) 2011 Web Notes Technologies
# Chai Project may be freely distributed under MIT license
# Authors: Rushabh Mehta (@rushabh_mehta)

class HTTPRequest:
	"""
	Wrapper around HTTPRequest

	- selects database
	- manages session
	- calls "action"

	"""
	def __init__(self):
		self.action = None
		self.database = None
		
		self.set_cookies()
		self.connect_db()
		self.load_session()
	
	def set_cookies(self):
		"""
		Builds cookies dictionary
		"""
		def get_incoming_cookies(self):
			import os
			import Cookie

			cookies = Cookie.SimpleCookie()
			self.cookies = {}
			
			if 'HTTP_COOKIE' in os.environ:
				c = os.environ['HTTP_COOKIE']
				cookies.load(c)
				
				for c in cookies.values():
					self.cookies[c.key] = c.value

	def connect_db(self):
		"""
		Selects db
		"""
		if self.cookies.get('db'):
			config.db_name = self.cookies['db']
		
		from sqlachemy import create_engine, sessionmaker
		
		chai.db_engine = create_engine('mysql://%(db_user)s:%(db_password)s@localhost/%(db_name)s', config.__dict__)
		chai.db_session = sessionmaker(bind = chai.db_engine)()
		
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
				chai.msg('Unpermitted action')
				