# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cint, now, get_gravatar
from frappe import throw, msgprint, _
from frappe.auth import _update_password
from frappe.desk.notifications import clear_notifications
import frappe.permissions

STANDARD_USERS = ("Guest", "Administrator")

from frappe.model.document import Document

class User(Document):
	def autoname(self):
		"""set name as email id"""
		if self.name not in STANDARD_USERS:
			self.email = self.email.strip()
			self.name = self.email

	def validate(self):
		self.in_insert = self.get("__islocal")
		if self.name not in STANDARD_USERS:
			self.validate_email_type(self.email)
		self.add_system_manager_role()
		self.validate_system_manager_user_type()
		self.check_enable_disable()
		self.update_gravatar()
		self.ensure_unique_roles()
		self.remove_all_roles_for_guest()
		if self.language == "Loading...":
			self.language = None

	def check_enable_disable(self):
		# do not allow disabling administrator/guest
		if not cint(self.enabled) and self.name in STANDARD_USERS:
			frappe.throw(_("User {0} cannot be disabled").format(self.name))

		if not cint(self.enabled):
			self.a_system_manager_should_exist()

		# clear sessions if disabled
		if not cint(self.enabled) and getattr(frappe.local, "login_manager", None):
			frappe.local.login_manager.logout(user=self.name)

	def add_system_manager_role(self):
		# if adding system manager, do nothing
		if not cint(self.enabled) or ("System Manager" in [user_role.role for user_role in
				self.get("user_roles")]):
			return

		if self.name not in STANDARD_USERS and self.user_type == "System User" and not self.get_other_system_managers():
			msgprint(_("Adding System Manager to this User as there must be atleast one System Manager"))
			self.append("user_roles", {
				"doctype": "UserRole",
				"role": "System Manager"
			})

	def validate_system_manager_user_type(self):
		#if user has system manager role then user type should be system user
		if ("System Manager" in [user_role.role for user_role in
			self.get("user_roles")]) and self.get("user_type") != "System User":
				frappe.throw(_("User with System Manager Role should always have User Type: System User"))

	def email_new_password(self, new_password=None):
		if new_password and not self.in_insert:
			_update_password(self.name, new_password)

			self.password_update_mail(new_password)
			frappe.msgprint(_("New password emailed"))

	def on_update(self):
		# owner is always name
		frappe.db.set(self, 'owner', self.name)

		# clear new password
		new_password = self.new_password
		self.db_set("new_password", "")

		clear_notifications(user=self.name)
		frappe.clear_cache(user=self.name)

		try:
			if self.in_insert:
				if self.name not in STANDARD_USERS:
					if new_password:
						# new password given, no email required
						_update_password(self.name, new_password)
					if not getattr(self, "no_welcome_mail", False):
						self.send_welcome_mail()
						msgprint(_("Welcome email sent"))
						return
			else:
				self.email_new_password(new_password)

		except frappe.OutgoingEmailError:
			pass # email server not set, don't send email

	def update_gravatar(self):
		if not self.user_image:
			self.user_image = get_gravatar(self.name)

	@Document.hook
	def validate_reset_password(self):
		pass

	def reset_password(self):
		from frappe.utils import random_string, get_url

		key = random_string(32)
		self.db_set("reset_password_key", key)
		self.password_reset_mail(get_url("/update-password?key=" + key))

	def get_other_system_managers(self):
		return frappe.db.sql("""select distinct user.name from tabUserRole user_role, tabUser user
			where user_role.role='System Manager'
				and user.docstatus<2
				and ifnull(user.enabled,0)=1
				and user_role.parent = user.name
			and user_role.parent not in ('Administrator', %s) limit 1""", (self.name,))

	def get_fullname(self):
		"""get first_name space last_name"""
		return (self.first_name or '') + \
			(self.first_name and " " or '') + (self.last_name or '')

	def password_reset_mail(self, link):
		self.send_login_mail(_("Password Reset"), "templates/emails/password_reset.html", {"link": link})

	def password_update_mail(self, password):
		self.send_login_mail(_("Password Update"), "templates/emails/password_update.html", {"new_password": password})

	def send_welcome_mail(self):
		from frappe.utils import random_string, get_url

		key = random_string(32)
		self.db_set("reset_password_key", key)
		link = get_url("/update-password?key=" + key)

		self.send_login_mail(_("Verify Your Account"), "templates/emails/new_user.html", {"link": link})

	def send_login_mail(self, subject, template, add_args):
		"""send mail with login details"""
		from frappe.utils.user import get_user_fullname
		from frappe.utils import get_url

		mail_titles = frappe.get_hooks().get("login_mail_title", [])
		title = frappe.db.get_default('company') or (mail_titles and mail_titles[0]) or ""

		full_name = get_user_fullname(frappe.session['user'])
		if full_name == "Guest":
			full_name = "Administrator"

		args = {
			'first_name': self.first_name or self.last_name or "user",
			'user': self.name,
			'title': title,
			'login_url': get_url(),
			'user_fullname': full_name
		}

		args.update(add_args)

		sender = frappe.session.user not in STANDARD_USERS and frappe.session.user or None

		frappe.sendmail(recipients=self.email, sender=sender, subject=subject,
			message=frappe.get_template(template).render(args))

	def a_system_manager_should_exist(self):
		if not self.get_other_system_managers():
			throw(_("There should remain at least one System Manager"))

	def on_trash(self):
		frappe.clear_cache(user=self.name)
		if self.name in STANDARD_USERS:
			throw(_("User {0} cannot be deleted").format(self.name))

		self.a_system_manager_should_exist()

		# disable the user and log him/her out
		self.enabled = 0
		if getattr(frappe.local, "login_manager", None):
			frappe.local.login_manager.logout(user=self.name)

		# delete their password
		frappe.db.sql("""delete from __Auth where user=%s""", (self.name,))

		# delete todos
		frappe.db.sql("""delete from `tabToDo` where owner=%s""", (self.name,))
		frappe.db.sql("""update tabToDo set assigned_by=null where assigned_by=%s""",
			(self.name,))

		# delete events
		frappe.db.sql("""delete from `tabEvent` where owner=%s
			and event_type='Private'""", (self.name,))
		frappe.db.sql("""delete from `tabEvent User` where person=%s""", (self.name,))

		# delete messages
		frappe.db.sql("""delete from `tabComment` where comment_doctype='Message'
			and (comment_docname=%s or owner=%s)""", (self.name, self.name))

	def before_rename(self, olddn, newdn, merge=False):
		frappe.clear_cache(user=olddn)
		self.validate_rename(olddn, newdn)

	def validate_rename(self, olddn, newdn):
		# do not allow renaming administrator and guest
		if olddn in STANDARD_USERS:
			throw(_("User {0} cannot be renamed").format(self.name))

		self.validate_email_type(newdn)

	def validate_email_type(self, email):
		from frappe.utils import validate_email_add

		email = email.strip()
		if not validate_email_add(email):
			throw(_("{0} is not a valid email id").format(email))

	def after_rename(self, olddn, newdn, merge=False):
		tables = frappe.db.sql("show tables")
		for tab in tables:
			desc = frappe.db.sql("desc `%s`" % tab[0], as_dict=1)
			has_fields = []
			for d in desc:
				if d.get('Field') in ['owner', 'modified_by']:
					has_fields.append(d.get('Field'))
			for field in has_fields:
				frappe.db.sql("""\
					update `%s` set `%s`=%s
					where `%s`=%s""" % \
					(tab[0], field, '%s', field, '%s'), (newdn, olddn))

		# set email
		frappe.db.sql("""\
			update `tabUser` set email=%s
			where name=%s""", (newdn, newdn))

		# update __Auth table
		if not merge:
			frappe.db.sql("""update __Auth set user=%s where user=%s""", (newdn, olddn))

	def add_roles(self, *roles):
		for role in roles:
			if role in [d.role for d in self.get("user_roles")]:
				continue
			self.append("user_roles", {
				"doctype": "UserRole",
				"role": role
			})

		self.save()

	def remove_roles(self, *roles):
		existing_roles = dict((d.role, d) for d in self.get("user_roles"))
		for role in roles:
			if role in existing_roles:
				self.get("user_roles").remove(existing_roles[role])

		self.save()

	def remove_all_roles_for_guest(self):
		if self.name == "Guest":
			self.set("user_roles", list(set(d for d in self.get("user_roles") if d.role == "Guest")))

	def ensure_unique_roles(self):
		exists = []
		for i, d in enumerate(self.get("user_roles")):
			if (not d.role) or (d.role in exists):
				self.get("user_roles").remove(d)
			else:
				exists.append(d.role)

@frappe.whitelist()
def get_languages():
	from frappe.translate import get_lang_dict
	import pytz
	languages = get_lang_dict().keys()
	languages.sort()
	return {
		"languages": [""] + languages,
		"timezones": pytz.all_timezones
	}

@frappe.whitelist()
def get_all_roles(arg=None):
	"""return all roles"""
	return [r[0] for r in frappe.db.sql("""select name from tabRole
		where name not in ('Administrator', 'Guest', 'All') order by name""")]

@frappe.whitelist()
def get_user_roles(arg=None):
	"""get roles for a user"""
	return frappe.get_roles(frappe.form_dict['uid'])

@frappe.whitelist()
def get_perm_info(arg=None):
	"""get permission info"""
	return frappe.db.sql("""select * from tabDocPerm where role=%s
		and docstatus<2 order by parent, permlevel""", (frappe.form_dict['role'],), as_dict=1)

@frappe.whitelist(allow_guest=True)
def update_password(new_password, key=None, old_password=None):
	# verify old password
	if key:
		user = frappe.db.get_value("User", {"reset_password_key":key})
		if not user:
			return _("Cannot Update: Incorrect / Expired Link.")
	elif old_password:
		user = frappe.session.user
		if not frappe.db.sql("""select user from __Auth where password=password(%s)
			and user=%s""", (old_password, user)):
			return _("Cannot Update: Incorrect Password")

	_update_password(user, new_password)

	frappe.db.set_value("User", user, "reset_password_key", "")

	frappe.local.login_manager.logout()

	return _("Password Updated")

@frappe.whitelist(allow_guest=True)
def sign_up(email, full_name):
	user = frappe.db.get("User", {"email": email})
	if user:
		if user.disabled:
			return _("Registered but disabled.")
		else:
			return _("Already Registered")
	else:
		if frappe.db.sql("""select count(*) from tabUser where
			HOUR(TIMEDIFF(CURRENT_TIMESTAMP, TIMESTAMP(modified)))=1""")[0][0] > 200:
			frappe.msgprint("Login is closed for sometime, please check back again in an hour.")
			raise Exception, "Too Many New Users"
		from frappe.utils import random_string
		user = frappe.get_doc({
			"doctype":"User",
			"email": email,
			"first_name": full_name,
			"enabled": 1,
			"new_password": random_string(10),
			"user_type": "Website User"
		})
		user.ignore_permissions = True
		user.insert()
		return _("Registration Details Emailed.")

@frappe.whitelist(allow_guest=True)
def reset_password(user):
	if user=="Administrator":
		return _("Not allowed to reset the password of {0}").format(user)

	try:
		user = frappe.get_doc("User", user)
		user.validate_reset_password()
		user.reset_password()

		return _("Password reset instructions have been sent to your email")

	except frappe.DoesNotExistError:
		return _("User {0} does not exist").format(user)

def user_query(doctype, txt, searchfield, start, page_len, filters):
	from frappe.desk.reportview import get_match_cond
	txt = "%{}%".format(txt)
	return frappe.db.sql("""select name, concat_ws(' ', first_name, middle_name, last_name)
		from `tabUser`
		where ifnull(enabled, 0)=1
			and docstatus < 2
			and name not in ({standard_users})
			and user_type != 'Website User'
			and ({key} like %s
				or concat_ws(' ', first_name, middle_name, last_name) like %s)
			{mcond}
		order by
			case when name like %s then 0 else 1 end,
			case when concat_ws(' ', first_name, middle_name, last_name) like %s
				then 0 else 1 end,
			name asc
		limit %s, %s""".format(standard_users=", ".join(["%s"]*len(STANDARD_USERS)),
			key=searchfield, mcond=get_match_cond(doctype)),
			tuple(list(STANDARD_USERS) + [txt, txt, txt, txt, start, page_len]))

def get_total_users(exclude_users=None):
	"""Returns total no. of system users"""
	return len(get_system_users(exclude_users=exclude_users))

def get_system_users(exclude_users=None):
	if not exclude_users:
		exclude_users = []
	elif not isinstance(exclude_users, (list, tuple)):
		exclude_users = [exclude_users]

	exclude_users += list(STANDARD_USERS)

	system_users = frappe.db.sql_list("""select name from `tabUser`
		where enabled=1 and user_type != 'Website User'
		and name not in ({})""".format(", ".join(["%s"]*len(exclude_users))),
		exclude_users)

	return system_users

def get_active_users():
	"""Returns No. of system users who logged in, in the last 3 days"""
	return frappe.db.sql("""select count(*) from `tabUser`
		where enabled = 1 and user_type != 'Website User'
		and name not in ({})
		and hour(timediff(now(), last_login)) < 72""".format(", ".join(["%s"]*len(STANDARD_USERS))), STANDARD_USERS)[0][0]

def get_website_users():
	"""Returns total no. of website users"""
	return frappe.db.sql("""select count(*) from `tabUser`
		where enabled = 1 and user_type = 'Website User'""")[0][0]

def get_active_website_users():
	"""Returns No. of website users who logged in, in the last 3 days"""
	return frappe.db.sql("""select count(*) from `tabUser`
		where enabled = 1 and user_type = 'Website User'
		and hour(timediff(now(), last_login)) < 72""")[0][0]

def get_permission_query_conditions(user):
	if user=="Administrator":
		return ""

	else:
		return """(`tabUser`.name not in ({standard_users}))""".format(
			standard_users='"' + '", "'.join(STANDARD_USERS) + '"')

def has_permission(doc, user):
	if (user != "Administrator") and (doc.name in STANDARD_USERS):
		# dont allow non Administrator user to view / edit Administrator user
		return False

	else:
		return True
