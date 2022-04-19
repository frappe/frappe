# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import json

import frappe
import frappe.share
from frappe import _dict
from frappe.boot import get_allowed_reports
from frappe.core.doctype.domain_settings.domain_settings import get_active_modules
from frappe.permissions import get_roles, get_valid_perms
from frappe.utils import cint


class UserPermissions:
	"""
	A user permission object can be accessed as `frappe.get_user()`
	"""

	def __init__(self, name=""):
		self.defaults = None
		self.name = name or frappe.session.get("user")
		self.roles = []

		self.all_read = []
		self.can_create = []
		self.can_select = []
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
			except Exception as e:
				# install boo-boo
				if not frappe.db.is_table_missing(e):
					raise

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

	def build_doctype_map(self):
		"""build map of special doctype properties"""

		active_domains = frappe.get_active_domains()

		self.doctype_map = {}
		for r in frappe.db.sql(
			"""select name, in_create, issingle, istable,
			read_only, restrict_to_domain, module from tabDocType""",
			as_dict=1,
		):
			if (not r.restrict_to_domain) or (r.restrict_to_domain in active_domains):
				self.doctype_map[r["name"]] = r

	def build_perm_map(self):
		"""build map of permissions at level 0"""
		self.perm_map = {}
		for r in get_valid_perms():
			dt = r["parent"]

			if not dt in self.perm_map:
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
		no_list_view_link = []
		active_modules = get_active_modules() or []
		for dt in self.doctype_map:
			dtp = self.doctype_map[dt]

			p = self.perm_map.get(dt, {})

			if not p.get("read") and (dt in user_shared):
				p["read"] = 1

			if p.get("select"):
				self.can_select.append(dt)

			if not dtp.get("istable"):
				if p.get("create") and not dtp.get("issingle"):
					if dtp.get("in_create"):
						self.in_create.append(dt)
					else:
						self.can_create.append(dt)
				elif p.get("write"):
					self.can_write.append(dt)
				elif p.get("read"):
					if dtp.get("read_only"):
						# read_only = "User Cannot Search"
						self.all_read.append(dt)
						no_list_view_link.append(dt)
					else:
						self.can_read.append(dt)

			if p.get("cancel"):
				self.can_cancel.append(dt)

			if p.get("delete"):
				self.can_delete.append(dt)

			if p.get("read") or p.get("write") or p.get("create"):
				if p.get("report"):
					self.can_get_report.append(dt)
				for key in ("import", "export", "print", "email", "set_user_permissions"):
					if p.get(key):
						getattr(self, "can_" + key).append(dt)

				if not dtp.get("istable"):
					if not dtp.get("issingle") and not dtp.get("read_only"):
						self.can_search.append(dt)
					if dtp.get("module") not in self.allow_modules:
						if active_modules and dtp.get("module") not in active_modules:
							pass
						else:
							self.allow_modules.append(dtp.get("module"))

		self.can_write += self.can_create
		self.can_write += self.in_create
		self.can_read += self.can_write

		self.shared = frappe.db.sql_list(
			"""select distinct share_doctype from `tabDocShare`
			where `user`=%s and `read`=1""",
			self.name,
		)
		self.can_read = list(set(self.can_read + self.shared))

		self.all_read += self.can_read

		for dt in no_list_view_link:
			if dt in self.can_read:
				self.can_read.remove(dt)

		if "System Manager" in self.get_roles():
			docs = frappe.get_all("DocType", {"allow_import": 1})
			self.can_import += [doc.name for doc in docs]

			customizations = frappe.get_all(
				"Property Setter", fields=["doc_type"], filters={"property": "allow_import", "value": "1"}
			)
			self.can_import += [custom.doc_type for custom in customizations]

		frappe.cache().hset("can_import", frappe.session.user, self.can_import)

	def get_defaults(self):
		import frappe.defaults

		self.defaults = frappe.defaults.get_defaults(self.name)
		return self.defaults

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
		d = frappe.db.sql(
			"""select email, first_name, last_name, creation,
			email_signature, user_type, desk_theme, language,
			mute_sounds, send_me_a_copy, document_follow_notify
			from tabUser where name = %s""",
			(self.name,),
			as_dict=1,
		)[0]

		if not self.can_read:
			self.build_permissions()

		d.name = self.name
		d.roles = self.get_roles()
		d.defaults = self.get_defaults()
		for key in (
			"can_select",
			"can_create",
			"can_write",
			"can_read",
			"can_cancel",
			"can_delete",
			"can_get_report",
			"allow_modules",
			"all_read",
			"can_search",
			"in_create",
			"can_export",
			"can_import",
			"can_print",
			"can_email",
			"can_set_user_permissions",
		):
			d[key] = list(set(getattr(self, key)))

		d.all_reports = self.get_all_reports()
		return d

	def get_all_reports(self):
		return get_allowed_reports()


def get_user_fullname(user):
	fullname = frappe.db.sql(
		"SELECT CONCAT_WS(' ', first_name, last_name) FROM `tabUser` WHERE name=%s", (user,)
	)
	return fullname and fullname[0][0] or ""


def get_fullname_and_avatar(user):
	first_name, last_name, avatar, name = frappe.db.get_value(
		"User", user, ["first_name", "last_name", "user_image", "name"]
	)
	return _dict(
		{
			"fullname": " ".join(list(filter(None, [first_name, last_name]))),
			"avatar": avatar,
			"name": name,
		}
	)


def get_system_managers(only_name=False):
	"""returns all system manager's user details"""
	import email.utils

	from frappe.core.doctype.user.user import STANDARD_USERS

	system_managers = frappe.db.sql(
		"""SELECT DISTINCT `name`, `creation`,
		CONCAT_WS(' ',
			CASE WHEN `first_name`= '' THEN NULL ELSE `first_name` END,
			CASE WHEN `last_name`= '' THEN NULL ELSE `last_name` END
		) AS fullname
		FROM `tabUser` AS p
		WHERE `docstatus` < 2
		AND `enabled` = 1
		AND `name` NOT IN ({})
		AND exists
			(SELECT *
				FROM `tabHas Role` AS ur
				WHERE ur.parent = p.name
				AND ur.role='System Manager')
		ORDER BY `creation` DESC""".format(
			", ".join(["%s"] * len(STANDARD_USERS))
		),
		STANDARD_USERS,
		as_dict=True,
	)

	if only_name:
		return [p.name for p in system_managers]
	else:
		return [email.utils.formataddr((p.fullname, p.name)) for p in system_managers]


def add_role(user, role):
	frappe.get_doc("User", user).add_roles(role)


def add_system_manager(
	email, first_name=None, last_name=None, send_welcome_email=False, password=None
):
	# add user
	user = frappe.new_doc("User")
	user.update(
		{
			"name": email,
			"email": email,
			"enabled": 1,
			"first_name": first_name or email,
			"last_name": last_name,
			"user_type": "System User",
			"send_welcome_email": 1 if send_welcome_email else 0,
		}
	)

	user.insert()

	# add roles
	roles = frappe.get_all(
		"Role", fields=["name"], filters={"name": ["not in", ("Administrator", "Guest", "All")]}
	)
	roles = [role.name for role in roles]
	user.add_roles(*roles)

	if password:
		from frappe.utils.password import update_password

		update_password(user=user.name, pwd=password)


def get_enabled_system_users():
	# add more fields if required
	return frappe.get_all(
		"User",
		fields=["email", "language", "name"],
		filters={
			"user_type": "System User",
			"enabled": 1,
			"name": ["not in", ("Administrator", "Guest")],
		},
	)


def is_website_user():
	return frappe.db.get_value("User", frappe.session.user, "user_type") == "Website User"


def is_system_user(username):
	return frappe.db.get_value("User", {"email": username, "enabled": 1, "user_type": "System User"})


def get_users():
	from frappe.core.doctype.user.user import get_system_users

	users = []
	system_managers = frappe.utils.user.get_system_managers(only_name=True)
	for user in get_system_users():
		users.append(
			{
				"full_name": frappe.utils.user.get_user_fullname(user),
				"email": user,
				"is_system_manager": 1 if (user in system_managers) else 0,
			}
		)

	return users


def set_last_active_to_now(user):
	from frappe.utils import now_datetime

	frappe.db.set_value("User", user, "last_active", now_datetime())


def reset_simultaneous_sessions(user_limit):
	for user in frappe.db.sql(
		"""select name, simultaneous_sessions from tabUser
		where name not in ('Administrator', 'Guest') and user_type = 'System User' and enabled=1
		order by creation desc""",
		as_dict=1,
	):
		if user.simultaneous_sessions < user_limit:
			user_limit = user_limit - user.simultaneous_sessions
		else:
			frappe.db.set_value("User", user.name, "simultaneous_sessions", 1)
			user_limit = user_limit - 1


def get_link_to_reset_password(user):
	link = ""

	if not cint(frappe.db.get_single_value("System Settings", "setup_complete")):
		user = frappe.get_doc("User", user)
		link = user.reset_password(send_email=False)
		frappe.db.commit()

	return {"link": link}


def get_users_with_role(role):
	return [
		p[0]
		for p in frappe.db.sql(
			"""SELECT DISTINCT `tabUser`.`name`
		FROM `tabHas Role`, `tabUser`
		WHERE `tabHas Role`.`role`=%s
		AND `tabUser`.`name`!='Administrator'
		AND `tabHas Role`.`parent`=`tabUser`.`name`
		AND `tabUser`.`enabled`=1""",
			role,
		)
	]
