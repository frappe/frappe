# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
# MIT License. See license.txt 

from __future__ import unicode_literals

import webnotes, json

class Profile:
	"""
	A profile object is created at the beginning of every request with details of the use.
	The global profile object is `webnotes.user`
	"""
	def __init__(self, name=''):
		self.defaults = None
		self.name = name or webnotes.session.get('user')
		self.roles = []
		
		self.all_read = []
		self.can_create = []
		self.can_read = []
		self.can_write = []
		self.can_cancel = []
		self.can_search = []
		self.can_get_report = []
		self.allow_modules = []
		self.in_create = []

	def get_roles(self):
		"""get list of roles"""
		if not self.roles:
			self.roles = webnotes.get_roles(self.name)
		return self.roles
	
	def build_doctype_map(self):
		"""build map of special doctype properties"""
			
		self.doctype_map = {}
		for r in webnotes.conn.sql("""select name, in_create, issingle, istable, 
			read_only, module from tabDocType""", as_dict=1):
			self.doctype_map[r['name']] = r
			
	def build_perm_map(self):
		"""build map of permissions at level 0"""
		
		self.perm_map = {}
		for r in webnotes.conn.sql("""select parent, `read`, `write`, `create`, `submit`, `cancel`, `report` 
			from tabDocPerm where docstatus=0 
			and ifnull(permlevel,0)=0
			and parent not like "old_parent:%%" 
			and role in ('%s')""" % "','".join(self.get_roles()), as_dict=1):
			
			dt = r['parent']
			
			if not dt in  self.perm_map:
				self.perm_map[dt] = {}
				
			for k in ('read', 'write', 'create', 'submit', 'cancel', 'report'):
				if not self.perm_map[dt].get(k):
					self.perm_map[dt][k] = r.get(k)
						
	def build_permissions(self):
		"""build lists of what the user can read / write / create
		quirks: 
			read_only => Not in Search
			in_create => Not in create
		"""
		self.build_doctype_map()
		self.build_perm_map()
				
		for dt in self.doctype_map:
			dtp = self.doctype_map[dt]
			p = self.perm_map.get(dt, {})

			if not dtp.get('istable'):
				if p.get('create') and not dtp.get('issingle'):
					if dtp.get('in_create'):
						self.in_create.append(dt)
					else:
						self.can_create.append(dt)
				elif p.get('write'):
					self.can_write.append(dt)
				elif p.get('read'):
					if dtp.get('read_only'):
						self.all_read.append(dt)
					else:
						self.can_read.append(dt)

			if p.get('cancel'):
				self.can_cancel.append(dt)

			if (p.get('read') or p.get('write') or p.get('create')):
				if p.get('report'):
					self.can_get_report.append(dt)
				if not dtp.get('istable'):
					if not dtp.get('issingle') and not dtp.get('read_only'):
						self.can_search.append(dt)
					if not dtp.get('module') in self.allow_modules:
						self.allow_modules.append(dtp.get('module'))

		self.can_write += self.can_create
		self.can_write += self.in_create
		self.can_read += self.can_write
		self.all_read += self.can_read

	def get_defaults(self):
		import webnotes.defaults
		self.defaults = webnotes.defaults.get_defaults(self.name)
		return self.defaults
			
	# update recent documents
	def update_recent(self, dt, dn):
		rdl = webnotes.cache().get_value("recent:" + self.name) or []	
		new_rd = [dt, dn]
		
		# clear if exists
		for i in range(len(rdl)):
			rd = rdl[i]
			if rd==new_rd:
				del rdl[i]
				break

		if len(rdl) > 19:
			rdl = rdl[:19]
		
		rdl = [new_rd] + rdl
		r = webnotes.cache().set_value("recent:" + self.name, rdl)
	
	def get_can_read(self):
		"""return list of doctypes that the user can read"""
		if not self.can_read:
			self.build_permissions()
		return self.can_read
	
	def load_profile(self):
		d = webnotes.conn.sql("""select email, first_name, last_name, 
			email_signature, background_image, user_type
			from tabProfile where name = %s""", self.name, as_dict=1)[0]

		if not self.can_read:
			self.build_permissions()

		d.name = self.name
		d.recent = json.dumps(webnotes.cache().get_value("recent:" + self.name) or [])
				
		d['roles'] = self.get_roles()
		d['defaults'] = self.get_defaults()
		d['can_create'] = self.can_create
		d['can_write'] = self.can_write
		d['can_read'] = list(set(self.can_read))
		d['can_cancel'] = list(set(self.can_cancel))
		d['can_get_report'] = list(set(self.can_get_report))
		d['allow_modules'] = self.allow_modules
		d['all_read'] = self.all_read
		d['can_search'] = list(set(self.can_search))
		d['in_create'] = self.in_create
		
		return d
		
def get_user_fullname(user):
	fullname = webnotes.conn.sql("SELECT CONCAT_WS(' ', first_name, last_name) FROM `tabProfile` WHERE name=%s", user)
	return fullname and fullname[0][0] or ''

def get_system_managers():
	"""returns all system manager's profile details"""
	system_managers = webnotes.conn.sql("""select distinct name
		from tabProfile p 
		where docstatus < 2 and enabled = 1
		and name not in ("Administrator", "Guest")
		and exists (select * from tabUserRole ur
			where ur.parent = p.name and ur.role="System Manager")""")
	
	return [p[0] for p in system_managers]
	
def add_role(profile, role):
	profile_wrapper = webnotes.bean("Profile", profile)
	profile_wrapper.doclist.append({
		"doctype": "UserRole",
		"parentfield": "user_roles",
		"role": role
	})
	profile_wrapper.save()
