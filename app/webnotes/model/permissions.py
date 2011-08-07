class PermissionChecker:
	"""
		Checks if model has permissions
	"""
	def __init__(self, model):
		self.model = model
	
	def load_perms(self):
		if not self._perms:
			self._perms = webnotes.conn.sql("""
				select role, `match` from tabDocPerm 
				where parent=%s 
				and ifnull(`read`,0) = 1 
				and ifnull(permlevel,0)=0""", self.model.type)

	def load_roles(self):
		"""
			Load roles
		"""
		if not self._roles:
			if webnotes.user:
				self._roles = webnotes.user.get_roles()
			else:
				self._roles = ['Guest']

	def load_defaults(self):
		if not self._user_defaults:
			if webnotes.user:
				self._user_defaults = webnotes.user.get_defaults()
			else:
				self.defaults = {}

	def has_perm(self, verbose=0):
		"""
			Returns 1 if the user has permission on the given model
		"""
		import webnotes
		
		# Admin has all permissions
		if webnotes.session['user']=='Administrator':
			return 1
		
		# find roles with read access for this record at 0
		self.load_perms()
		self.load_roles()
		self.load_defaults()
	
		has_perm, match = 0, []
		
		values = self.model.get_values()
		
		# loop through everything to find if there is a match
		for r in self._perms:
			if r[0] in self._roles:
				has_perm = 1
				if r[1] and match != -1:
					match.append(r[1]) # add to match check
				else:
					match = -1 # has permission and no match, so match not required!
		
		if has_perm and match and match != -1:
			for m in match:
				if values.get(m, 'no value') in self._user_defaults.get(m, 'no default'):
					has_perm = 1
					break # permission found! break
				else:
					has_perm = 0
					if verbose:
						webnotes.msgprint("Value not allowed: '%s' for '%s'" % (values.get(m, 'no value'), m))
					
	
		# check for access key
		if webnotes.form and webnotes.form.has_key('akey'):
			import webnotes.utils.encrypt
			if webnotes.utils.encrypt.decrypt(webnotes.form.getvalue('akey')) == self.model.name:
				has_perm = 1
				webnotes.response['print_access'] = 1
				
		return has_perm
	