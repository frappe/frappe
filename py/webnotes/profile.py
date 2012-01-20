import webnotes

class Profile:
	"""
	A profile object is created at the beginning of every request with details of the use.
	The global profile object is `webnotes.user`
	"""
	def __init__(self, name=''):
		self.name = name or webnotes.session.get('user')
		self.roles = []

		self.can_create = []
		self.can_read = []
		self.can_write = []
		self.can_get_report = []
		
	def _load_roles(self):
		res = webnotes.conn.sql('select role from tabUserRole where parent = "%s"' % self.name)
		self.roles = []
		for t in res:
			if t[0]: self.roles.append(t[0])
		if webnotes.session.get('user') == 'Guest':
			self.roles.append('Guest')
		else:
			self.roles.append('All')
			
		return self.roles

	def get_roles(self):
		"""
		get list of roles
		"""
		if self.roles:
			return self.roles
		
		return self._load_roles()
	
	def get_allow_list(self, key):
		"""
	      	Internal - get list of DocType where `key` is allowed. Key is either 'read', 'write' or 'create'
		"""
		conn = webnotes.conn
		roles = self.get_roles()
		return [r[0] for r in conn.sql('SELECT DISTINCT t1.parent FROM `tabDocPerm` t1, tabDocType t2 WHERE t1.`%s`=1 AND t1.parent not like "old_parent:%%" AND t1.parent = t2.name AND IFNULL(t2.istable,0) = 0 AND t1.role in ("%s") order by t1.parent' % (key, '", "'.join(roles)))]
	
	def get_create_list(self):
		"""
		Get list of DocTypes the user can create. Will filter DocTypes tagged with 'not_in_create' and table
		"""
		cl = self.get_allow_list('create')
		conn = webnotes.conn
		no_create_list = [r[0] for r in conn.sql('select name from tabDocType where ifnull(in_create,0)=1 or ifnull(istable,0)=1 or ifnull(issingle,0)=1')]
		self.can_create = filter(lambda x: x not in no_create_list, cl)
		return self.can_create
		
	def get_read_list(self):
		"""
		Get list of DocTypes the user can read
		"""
		self.can_read = list(set(self.get_allow_list('read') + self.get_allow_list('write')))
		return self.can_read
	
	def get_report_list(self):

		conn = webnotes.conn
	
		# get all tables list
		res = conn.sql('SELECT parent, options from tabDocField where fieldtype="Table"')
		table_types, all_tabletypes = {}, []
		
		# make a dictionary fo all table types
		for t in res: 
			all_tabletypes.append(t[1])
			if not table_types.has_key(t[0]):
				table_types[t[0]] = []
			table_types[t[0]].append(t[1])
	
		no_search_list = [r[0] for r in conn.sql('SELECT name FROM tabDocType WHERE read_only = 1 ORDER BY name')]
		# make the lists
		for f in self.can_read:
			tl = table_types.get(f, None)
			if tl:
				for t in tl:
					if t and (not t in self.can_get_report) and (not t in no_search_list):
						self.can_get_report.append(t)
			
			if f and (not f in self.can_get_report) and (not f in no_search_list): 
				self.can_get_report.append(f)
	
		return self.can_get_report
		
	def get_write_list(self):
		"""
		Get list of DocTypes the user can write
		"""	
		self.can_write = self.get_allow_list('write')
		return self.can_write

	def get_home_page(self):
		"""
		Get the name of the user's home page from the `Control Panel`
		"""
		roles = self.get_roles()
		hpl = webnotes.conn.sql("select role, home_page from `tabDefault Home Page` where parent='Control Panel' order by idx asc")
		for h in hpl:
			if h[0] in roles:
				return h[1]

		return webnotes.conn.get_value('Control Panel',None,'home_page') or 'Login Page'

	def get_defaults(self):
		"""
		Get the user's default values based on user and role profile
		"""
		roles = self.get_roles() + [self.name]
		res = webnotes.conn.sql('select defkey, defvalue from `tabDefaultValue` where parent in ("%s")' % '", "'.join(roles))
	
		self.defaults = {'owner': [self.name,]}

		for rec in res: 
			if not self.defaults.has_key(rec[0]): 
				self.defaults[rec[0]] = []
			self.defaults[rec[0]].append(rec[1] or '')

		return self.defaults
		
	def get_hide_tips(self):
		try:
			return webnotes.conn.sql("select hide_tips from tabProfile where name=%s", self.name)[0][0] or 0
		except:
			return 0
			
	# update recent documents
	def update_recent(self, dt, dn):
		"""
		Update the user's `Recent` list with the given `dt` and `dn`
		"""
		conn = webnotes.conn
		from webnotes.utils import cstr
		import json

	
		# get list of child tables, so we know what not to add in the recent list
		child_tables = [t[0] for t in conn.sql('select name from tabDocType where istable = 1')]
		
		if not (dt in ['Print Format', 'Start Page', 'Event', 'ToDo Item', 'Search Criteria']) and not webnotes.is_testing and not (dt in child_tables):
			r = webnotes.conn.sql("select recent_documents from tabProfile where name=%s", self.name)[0][0] or ''

			
			# clear old style (to be removed)
			if '~~' in r: r = ''
			
			rdl = json.loads(r or '[]')
			new_rd = [dt, dn]
			
			# clear if exists
			for i in range(len(rdl)):
				rd = rdl[i]
				if rd==new_rd:
					del rdl[i]
					break

			rdl.append(new_rd)
			if len(rdl) > 20:
				rdl = rdl[:20]
			
			self.recent = json.dumps(rdl)
						
			webnotes.conn.sql("update tabProfile set recent_documents=%s where name=%s", (self.recent, self.name))
			
	def load_profile(self):
		"""
	      	Return a dictionary of user properites to be stored in the session
		"""
		t = webnotes.conn.sql('select email, first_name, last_name, recent_documents from tabProfile where name = %s', self.name)[0]

		d = {}
		d['name'] = self.name
		d['email'] = t[0] or ''
		d['first_name'] = t[1] or ''
		d['last_name'] = t[2] or ''
		d['recent'] = t[3] or ''
		
		d['hide_tips'] = self.get_hide_tips()
		
		d['roles'] = self.get_roles()
		d['defaults'] = self.get_defaults()
		
		d['can_create'] = self.get_create_list()
		d['can_read'] = self.get_read_list()
		d['can_write'] = self.get_write_list()
		d['can_get_report'] = self.get_report_list()
		
		return d
		
	def load_from_session(self, d):
		"""
		Setup the user profile from the dictionary saved in the session (generated by `load_profile`)
		"""
		self.can_create = d['can_create']
		self.can_read = d['can_read']
		self.can_write = d['can_write']
		self.can_get_report = d['can_get_report']

		self.roles = d['roles']
		self.defaults = d['defaults']

def get_user_img():
	if not webnotes.form.getvalue('username'):
		webnotes.response['message'] = 'no_img_m'
		return

	f = webnotes.conn.sql("select file_list from tabProfile where name=%s", webnotes.form.getvalue('username',''))
	if f:
		if f[0][0]:
			lst = f[0][0].split('\n')	
			webnotes.response['message'] = lst[0].split(',')[1]
		else:
			webnotes.response['message'] = 'no_img_m'		
	else:
		webnotes.response['message'] = 'no_img_m'
