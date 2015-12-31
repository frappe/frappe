# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe, json
from frappe import _dict
import frappe.share

class User:
	"""
	A user permission object can be accessed as `frappe.get_user()`
	"""
	def __init__(self, name=''):
		self.defaults = None
		self.name = name or frappe.session.get('user')
		self.roles = []

		self.all_read = []
		self.can_create = []
		self.can_read = []
		self.can_write = []
		self.can_cancel = []
		self.can_delete = []
		self.can_search = []
		self.can_get_report = []
		self.can_import = []
		self.can_export = []
		self.can_print = []
		self.can_email = []
		self.can_set_user_permissions = []
		self.allow_modules = []
		self.in_create = []
		self.setup_user()

	def setup_user(self):
		def get_user_doc():
			user = None
			try:
				user = frappe.get_doc("User", self.name).as_dict()
			except frappe.DoesNotExistError:
				pass
			except Exception, e:
				# install boo-boo
				if e.args[0] != 1146: raise

			return user

		if not frappe.flags.in_install_db and not frappe.flags.in_test:
			user_doc = frappe.cache().hget("user_doc", self.name, get_user_doc)
			if user_doc:
				self.doc = frappe.get_doc(user_doc)

	def get_roles(self):
		"""get list of roles"""
		if not self.roles:
			self.roles = get_roles(self.name)
		return self.roles

	def get_block_modules(self):
		"""Returns list of blocked modules"""
		return [d.module for d in self.doc.block_modules] if self.doc.block_modules else []

	def build_doctype_map(self):
		"""build map of special doctype properties"""

		self.doctype_map = {}
		for r in frappe.db.sql("""select name, in_create, issingle, istable,
			read_only, module from tabDocType""", as_dict=1):
			self.doctype_map[r['name']] = r

	def build_perm_map(self):
		"""build map of permissions at level 0"""
		self.perm_map = {}
		roles = self.get_roles()
		for r in frappe.db.sql("""select * from tabDocPerm where docstatus=0
			and ifnull(permlevel,0)=0
			and role in ({roles})""".format(roles=", ".join(["%s"]*len(roles))), tuple(roles), as_dict=1):
			dt = r['parent']

			if not dt in  self.perm_map:
				self.perm_map[dt] = {}

			for k in frappe.permissions.rights:
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
		user_shared = frappe.share.get_shared_doctypes()

		for dt in self.doctype_map:
			dtp = self.doctype_map[dt]
			p = self.perm_map.get(dt, {})

			if not p.get("read") and (dt in user_shared):
				p["read"] = 1

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

			if p.get('delete'):
				self.can_delete.append(dt)

			if (p.get('read') or p.get('write') or p.get('create')):
				if p.get('report'):
					self.can_get_report.append(dt)
				for key in ("import", "export", "print", "email", "set_user_permissions"):
					if p.get(key):
						getattr(self, "can_" + key).append(dt)

				if not dtp.get('istable'):
					if not dtp.get('issingle') and not dtp.get('read_only'):
						self.can_search.append(dt)
					if not dtp.get('module') in self.allow_modules:
						self.allow_modules.append(dtp.get('module'))

		self.can_write += self.can_create
		self.can_write += self.in_create
		self.can_read += self.can_write

		self.shared = frappe.db.sql_list("""select distinct share_doctype from `tabDocShare`
			where `user`=%s and `read`=1""", self.name)
		self.can_read = list(set(self.can_read + self.shared))

		self.all_read += self.can_read

		if "System Manager" in self.roles:
			self.can_import = frappe.db.sql_list("""select name from `tabDocType`
				where allow_import = 1""")

		self.all_reports = frappe.db.sql("""select name, report_type from tabReport
			where ref_doctype in ('{0}')""".format("', '".join(self.can_get_report)))

	def get_defaults(self):
		import frappe.defaults
		self.defaults = frappe.defaults.get_defaults(self.name)
		return self.defaults

	# update recent documents
	def update_recent(self, dt, dn):
		rdl = frappe.cache().hget("user_recent", self.name) or []
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

		frappe.cache().hset("user_recent", self.name, rdl)

	def _get(self, key):
		if not self.can_read:
			self.build_permissions()
		return getattr(self, key)

	def get_can_read(self):
		"""return list of doctypes that the user can read"""
		if not self.can_read:
			self.build_permissions()
		return self.can_read

	def load_user(self):
		d = frappe.db.sql("""select email, first_name, last_name,
			email_signature, user_type, language, background_image, background_style, mute_sounds
			from tabUser where name = %s""", (self.name,), as_dict=1)[0]

		if not self.can_read:
			self.build_permissions()

		d.name = self.name
		d.recent = json.dumps(frappe.cache().hget("user_recent", self.name) or [])

		d.roles = self.get_roles()
		d.defaults = self.get_defaults()
		d.block_modules = self.get_block_modules()

		for key in ("can_create", "can_write", "can_read", "can_cancel", "can_delete",
			"can_get_report", "allow_modules", "all_read", "can_search",
			"in_create", "can_export", "can_import", "can_print", "can_email",
			"can_set_user_permissions"):

			d[key] = list(set(getattr(self, key)))

		d.all_reports = dict(self.all_reports)
		return d

def get_user_fullname(user):
	fullname = frappe.db.sql("SELECT CONCAT_WS(' ', first_name, last_name) FROM `tabUser` WHERE name=%s", (user,))
	return fullname and fullname[0][0] or ''

def get_fullname_and_avatar(user):
	first_name, last_name, avatar = frappe.db.get_value("User",
		user, ["first_name", "last_name", "user_image"])
	return _dict({
		"fullname": " ".join(filter(None, [first_name, last_name])),
		"avatar": avatar
	})

def get_system_managers(only_name=False):
	"""returns all system manager's user details"""
	import email.utils
	from frappe.core.doctype.user.user import STANDARD_USERS
	system_managers = frappe.db.sql("""select distinct name,
		concat_ws(" ", if(first_name="", null, first_name), if(last_name="", null, last_name))
		as fullname from tabUser p
		where docstatus < 2 and enabled = 1
		and name not in ({})
		and exists (select * from tabUserRole ur
			where ur.parent = p.name and ur.role="System Manager")""".format(", ".join(["%s"]*len(STANDARD_USERS))),
			STANDARD_USERS, as_dict=True)

	if only_name:
		return [p.name for p in system_managers]
	else:
		return [email.utils.formataddr((p.fullname, p.name)) for p in system_managers]

def add_role(user, role):
	frappe.get_doc("User", user).add_roles(role)

def add_system_manager(email, first_name=None, last_name=None):
	# add user
	user = frappe.new_doc("User")
	user.update({
		"name": email,
		"email": email,
		"enabled": 1,
		"first_name": first_name or email,
		"last_name": last_name,
		"user_type": "System User"
	})
	user.insert()

	# add roles
	roles = frappe.db.sql_list("""select name from `tabRole`
		where name not in ("Administrator", "Guest", "All")""")
	user.add_roles(*roles)

def get_roles(user=None, with_standard=True):
	"""get roles of current user"""
	if not user:
		user = frappe.session.user

	if user=='Guest':
		return ['Guest']

	def get():
		return [r[0] for r in frappe.db.sql("""select role from tabUserRole
			where parent=%s and role not in ('All', 'Guest')""", (user,))] + ['All', 'Guest']

	roles = frappe.cache().hget("roles", user, get)

	# filter standard if required
	if not with_standard:
		roles = filter(lambda x: x not in ['All', 'Guest', 'Administrator'], roles)

	return roles

def get_enabled_system_users():
	return frappe.db.sql("""select * from tabUser where
		user_type='System User' and enabled=1 and name not in ('Administrator', 'Guest')""", as_dict=1)

def is_website_user():
	return frappe.get_user().doc.user_type == "Website User"

def is_system_user(username):
	return frappe.db.get_value("User", {"name": username, "enabled": 1, "user_type": "System User"})

def get_users():
	from frappe.core.doctype.user.user import get_system_users
	users = []
	system_managers = frappe.utils.user.get_system_managers(only_name=True)
	for user in get_system_users():
		users.append({
			"full_name": frappe.utils.user.get_user_fullname(user),
			"email": user,
			"is_system_manager": 1 if (user in system_managers) else 0
		})

	return users
