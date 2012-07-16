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

import webnotes

class Profile:
	"""
	A profile object is created at the beginning of every request with details of the use.
	The global profile object is `webnotes.user`
	"""
	def __init__(self, name=''):
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
		
	def _load_roles(self):
		self.roles = webnotes.get_roles()
		return self.roles

	def get_roles(self):
		"""get list of roles"""
		if self.roles:
			return self.roles
			
		return self._load_roles()
	
	def build_doctype_map(self):
		"""build map of special doctype properties"""
			
		self.doctype_map = {}
		for r in webnotes.conn.sql("""select name, in_create, issingle, istable, 
			read_only, module from tabDocType""", as_dict=1):
			r['child_tables'] = []
			self.doctype_map[r['name']] = r
			
		for r in webnotes.conn.sql("""select parent, options from tabDocField 
			where fieldtype="Table"
			and parent not like "old_parent:%%" 
			and ifnull(docstatus,0)=0
			"""):
			if r[0] in self.doctype_map:
				self.doctype_map[r[0]]['child_tables'].append(r[1])
	
	def build_perm_map(self):
		"""build map of permissions at level 0"""
		
		self.perm_map = {}
		for r in webnotes.conn.sql("""select parent, `read`, `write`, `create`, `submit`, `cancel` 
			from tabDocPerm where docstatus=0 
			and ifnull(permlevel,0)=0
			and parent not like "old_parent:%%" 
			and role in ('%s')""" % "','".join(self.get_roles()), as_dict=1):
			
			dt = r['parent']
			
			if not dt in  self.perm_map:
				self.perm_map[dt] = {}
				
			for k in ('read', 'write', 'create', 'submit', 'cancel'):
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
				if p.get('create') and not dtp.get('in_create') and \
						not dtp.get('issingle'):
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
				self.can_get_report.append(dt)
				self.can_get_report += dtp['child_tables']
				if not dtp.get('istable'):
					if not dtp.get('issingle') and not dtp.get('read_only'):
						self.can_search.append(dt)
					if not dtp.get('module') in self.allow_modules:
						self.allow_modules.append(dtp.get('module'))

		self.can_write += self.can_create
		self.can_read += self.can_write
		self.all_read += self.can_read

	def get_defaults(self):
		"""
		Get the user's default values based on user and role profile
		"""
		roles = self.get_roles() + [self.name]
		res = webnotes.conn.sql("""select defkey, defvalue 
		from `tabDefaultValue` where parent in ("%s") order by idx""" % '", "'.join(roles))
	
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
		child_tables = [t[0] for t in conn.sql('select name from tabDocType where ifnull(istable,0) = 1')]
		
		if not (dt in ['Print Format', 'Start Page', 'Event', 'ToDo', 'Search Criteria']) \
			and not (dt in child_tables):
			r = webnotes.conn.sql("select recent_documents from tabProfile where name=%s", \
				self.name)[0][0] or ''

			if '~~~' in r:
				r = '[]'
			
			rdl = json.loads(r or '[]')
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
			
			self.recent = json.dumps(rdl)
						
			webnotes.conn.sql("""update tabProfile set 
				recent_documents=%s where name=%s""", (self.recent, self.name))
			
	def load_profile(self):
		"""
	      	Return a dictionary of user properites to be stored in the session
		"""
		t = webnotes.conn.sql("""select email, first_name, last_name, 
			recent_documents from tabProfile where name = %s""", self.name)[0]

		if not self.can_read:
			self.build_permissions()

		d = {}
		d['name'] = self.name
		d['email'] = t[0] or ''
		d['first_name'] = t[1] or ''
		d['last_name'] = t[2] or ''
		d['recent'] = t[3] or ''
		
		d['hide_tips'] = self.get_hide_tips()
		
		d['roles'] = self.roles
		d['defaults'] = self.get_defaults()
		
		d['can_create'] = self.can_create
		d['can_write'] = self.can_write
		d['can_read'] = list(set(self.can_read))
		d['can_cancel'] = list(set(self.can_cancel))
		d['can_get_report'] = list(set(self.can_get_report))
		d['allow_modules'] = self.allow_modules
		d['all_read'] = self.all_read
		d['can_search'] = list(set(self.can_search))
		
		return d
		
	def load_from_session(self, d):
		"""
		Setup the user profile from the dictionary saved in the session (generated by `load_profile`)
		"""
		self.can_create = d['can_create']
		self.can_read = d['can_read']
		self.can_write = d['can_write']
		self.can_search = d['can_search']
		self.can_cancel = d['can_cancel']
		self.can_get_report = d['can_get_report']
		self.allow_modules = d['allow_modules']
		self.all_read = d['all_read']

		self.roles = d['roles']
		self.defaults = d['defaults']

	
	def reset_password(self):
		"""reset password"""
		from webnotes.utils import random_string, now
		pwd = random_string(8)
		
		# update tab Profile
		webnotes.conn.sql("""UPDATE tabProfile SET password=password(%s), modified=%s 
			WHERE name=%s""", (pwd, now(), self.name))

		return pwd


	def send_new_pwd(self, pwd):
		"""
			Send new password to user
		"""
		import os
		# send email
		with open(os.path.join(os.path.dirname(__file__), 'password_reset.txt'), 'r') as f:
			reset_password_mail = f.read()
		
		from webnotes.utils.email_lib import sendmail_md
		sendmail_md(recipients= self.name, \
			msg = reset_password_mail % {"user": get_user_fullname(self.name), "password": pwd}, \
			subject = 'Password Reset')




@webnotes.whitelist()
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


def get_user_fullname(user):
	fullname = webnotes.conn.sql("SELECT CONCAT_WS(' ', first_name, last_name) FROM `tabProfile` WHERE name=%s", user)
	return fullname and fullname[0][0] or ''
