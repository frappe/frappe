# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import cint, has_gravatar, format_datetime, now_datetime, get_formatted_email
from frappe import throw, msgprint, _
from frappe.utils.password import update_password as _update_password
from frappe.desk.notifications import clear_notifications
from frappe.utils.user import get_system_managers
import frappe.permissions
import frappe.share
import re
from frappe.limits import get_limits

STANDARD_USERS = ("Guest", "Administrator")

class MaxUsersReachedError(frappe.ValidationError): pass

class User(Document):
	__new_password = None

	def __setup__(self):
		# because it is handled separately
		self.flags.ignore_save_passwords = True

	def autoname(self):
		"""set name as email id"""
		if self.get("is_admin") or self.get("is_guest"):
			self.name = self.first_name
		else:
			self.email = self.email.strip()
			self.name = self.email

	def onload(self):
		self.set_onload('all_modules',
			[m.module_name for m in frappe.db.get_all('Desktop Icon',
				fields=['module_name'], filters={'standard': 1}, order_by="module_name")])

	def validate(self):
		self.check_demo()

		self.in_insert = self.get("__islocal")

		# clear new password
		self.__new_password = self.new_password
		self.new_password = ""

		if self.name not in STANDARD_USERS:
			self.validate_email_type(self.email)
		self.add_system_manager_role()
		self.set_system_user()
		self.set_full_name()
		self.check_enable_disable()
		self.update_gravatar()
		self.ensure_unique_roles()
		self.remove_all_roles_for_guest()
		self.validate_username()
		self.remove_disabled_roles()

		if self.language == "Loading...":
			self.language = None

	def on_update(self):
		# clear new password
		self.validate_user_limit()
		self.share_with_self()
		clear_notifications(user=self.name)
		frappe.clear_cache(user=self.name)
		self.send_password_notification(self.__new_password)

	def check_demo(self):
		if frappe.session.user == 'demo@erpnext.com':
			frappe.throw('Cannot change user details in demo. Please signup for a new account at https://erpnext.com', title='Not Allowed')

	def set_full_name(self):
		self.full_name = " ".join(filter(None, [self.first_name, self.last_name]))

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

		if self.name == 'Administrator':
			# Administrator should always have System Manager Role
			self.extend("user_roles", [
				{
					"doctype": "UserRole",
					"role": "System Manager"
				},
				{
					"doctype": "UserRole",
					"role": "Administrator"
				}
			])

	def email_new_password(self, new_password=None):
		if new_password and not self.in_insert:
			_update_password(self.name, new_password)

			if self.send_password_update_notification:
				self.password_update_mail(new_password)
				frappe.msgprint(_("New password emailed"))

	def set_system_user(self):
		if self.user_roles or self.name == 'Administrator':
			self.user_type = 'System User'
		else:
			self.user_type = 'Website User'

	def share_with_self(self):
		if self.user_type=="System User":
			frappe.share.add(self.doctype, self.name, self.name, share=1,
				flags={"ignore_share_permission": True})
		else:
			frappe.share.remove(self.doctype, self.name, self.name,
				flags={"ignore_share_permission": True, "ignore_permissions": True})

	def validate_share(self, docshare):
		if docshare.user == self.name:
			if self.user_type=="System User":
				if docshare.share != 1:
					frappe.throw(_("Sorry! User should have complete access to their own record."))
			else:
				frappe.throw(_("Sorry! Sharing with Website User is prohibited."))

	def send_password_notification(self, new_password):
		try:
			if self.in_insert:
				if self.name not in STANDARD_USERS:
					if new_password:
						# new password given, no email required
						_update_password(self.name, new_password)

					if not self.flags.no_welcome_mail and self.send_welcome_email:
						self.send_welcome_mail_to_user()
						msgprint(_("Welcome email sent"))
						return
			else:
				self.email_new_password(new_password)

		except frappe.OutgoingEmailError:
			pass # email server not set, don't send email


	def update_gravatar(self):
		if not self.user_image:
			self.user_image = has_gravatar(self.name)

	@Document.hook
	def validate_reset_password(self):
		pass

	def reset_password(self, send_email=False):
		from frappe.utils import random_string, get_url

		key = random_string(32)
		self.db_set("reset_password_key", key)
		link = get_url("/update-password?key=" + key)

		if send_email:
			self.password_reset_mail(link)

		return link

	def get_other_system_managers(self):
		return frappe.db.sql("""select distinct user.name from tabUserRole user_role, tabUser user
			where user_role.role='System Manager'
				and user.docstatus<2
				and user.enabled=1
				and user_role.parent = user.name
			and user_role.parent not in ('Administrator', %s) limit 1""", (self.name,))

	def get_fullname(self):
		"""get first_name space last_name"""
		return (self.first_name or '') + \
			(self.first_name and " " or '') + (self.last_name or '')

	def password_reset_mail(self, link):
		self.send_login_mail(_("Password Reset"),
			"templates/emails/password_reset.html", {"link": link}, now=True)

	def password_update_mail(self, password):
		self.send_login_mail(_("Password Update"),
			"templates/emails/password_update.html", {"new_password": password}, now=True)

	def send_welcome_mail_to_user(self):
		from frappe.utils import get_url

		link = self.reset_password()

		self.send_login_mail(_("Verify Your Account"), "templates/emails/new_user.html",
			{"link": link, "site_url": get_url()})


	def send_login_mail(self, subject, template, add_args, now=None):
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

		sender = frappe.session.user not in STANDARD_USERS and get_formatted_email(frappe.session.user) or None

		frappe.sendmail(recipients=self.email, sender=sender, subject=subject,
			message=frappe.get_template(template).render(args),
			delayed=(not now) if now!=None else self.flags.delay_emails, retry=3)

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

		# delete todos
		frappe.db.sql("""delete from `tabToDo` where owner=%s""", (self.name,))
		frappe.db.sql("""update tabToDo set assigned_by=null where assigned_by=%s""",
			(self.name,))

		# delete events
		frappe.db.sql("""delete from `tabEvent` where owner=%s
			and event_type='Private'""", (self.name,))

		# delete messages
		frappe.db.sql("""delete from `tabCommunication`
			where communication_type in ('Chat', 'Notification')
			and reference_doctype='User'
			and (reference_name=%s or owner=%s)""", (self.name, self.name))

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
		validate_email_add(email.strip(), True)

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

	def append_roles(self, *roles):
		"""Add roles to user"""
		current_roles = [d.role for d in self.get("user_roles")]
		for role in roles:
			if role in current_roles:
				continue
			self.append("user_roles", {"role": role})

	def add_roles(self, *roles):
		"""Add roles to user and save"""
		self.append_roles(*roles)
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

	def remove_disabled_roles(self):
		disabled_roles = [d.name for d in frappe.get_all("Role", filters={"disabled":1})]
		for role in list(self.get('user_roles')):
			if role.role in disabled_roles:
				self.get('user_roles').remove(role)

	def ensure_unique_roles(self):
		exists = []
		for i, d in enumerate(self.get("user_roles")):
			if (not d.role) or (d.role in exists):
				self.get("user_roles").remove(d)
			else:
				exists.append(d.role)

	def validate_username(self):
		if not self.username and self.is_new() and self.first_name:
			self.username = frappe.scrub(self.first_name)

		if not self.username:
			return

		# strip space and @
		self.username = self.username.strip(" @")

		if self.username_exists():
			if self.user_type == 'System User':
				frappe.msgprint(_("Username {0} already exists").format(self.username))
				self.suggest_username()

			self.username = ""

		# should be made up of characters, numbers and underscore only
		if self.username and not re.match(r"^[\w]+$", self.username):
			frappe.msgprint(_("Username should not contain any special characters other than letters, numbers and underscore"))
			self.username = ""

	def suggest_username(self):
		def _check_suggestion(suggestion):
			if self.username != suggestion and not self.username_exists(suggestion):
				return suggestion

			return None

		# @firstname
		username = _check_suggestion(frappe.scrub(self.first_name))

		if not username:
			# @firstname_last_name
			username = _check_suggestion(frappe.scrub("{0} {1}".format(self.first_name, self.last_name or "")))

		if username:
			frappe.msgprint(_("Suggested Username: {0}").format(username))

		return username

	def username_exists(self, username=None):
		return frappe.db.get_value("User", {"username": username or self.username, "name": ("!=", self.name)})

	def get_blocked_modules(self):
		"""Returns list of modules blocked for that user"""
		return [d.module for d in self.block_modules] if self.block_modules else []

	def validate_user_limit(self):
		'''
			Validate if user limit has been reached for System Users
			Checked in 'Validate' event as we don't want welcome email sent if max users are exceeded.
		'''

		if self.user_type == "Website User":
			return

		if not self.enabled:
			# don't validate max users when saving a disabled user
			return

		limits = get_limits()
		if not limits.users:
			# no limits defined
			return

		total_users = get_total_users()
		if self.is_new():
			# get_total_users gets existing users in database
			# a new record isn't inserted yet, so adding 1
			total_users += 1

		if total_users > limits.users:
			frappe.throw(_("Sorry. You have reached the maximum user limit for your subscription. You can either disable an existing user or buy a higher subscription plan."),
				MaxUsersReachedError)

@frappe.whitelist()
def get_timezones():
	import pytz
	return {
		"timezones": pytz.all_timezones
	}

@frappe.whitelist()
def get_all_roles(arg=None):
	"""return all roles"""
	return [r[0] for r in frappe.db.sql("""select name from tabRole
		where name not in ('Administrator', 'Guest', 'All') and not disabled order by name""")]

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
	res = _get_user_for_update_password(key, old_password)
	if res.get('message'):
		return res['message']
	else:
		user = res['user']

	_update_password(user, new_password)

	user_doc, redirect_url = reset_user_data(user)

	frappe.local.login_manager.login_as(user)

	if user_doc.user_type == "System User":
		return "/desk"
	else:
		return redirect_url if redirect_url else "/"

@frappe.whitelist(allow_guest=True)
def test_password_strength(new_password, key=None, old_password=None):
	from frappe.utils.password_strength import test_password_strength as _test_password_strength

	res = _get_user_for_update_password(key, old_password)
	if not res:
		return
	elif res.get('message'):
		return res['message']
	else:
		user = res['user']

	user_data = frappe.db.get_value('User', user, ['first_name', 'middle_name', 'last_name', 'email', 'birth_date'])

	if new_password:
		return _test_password_strength(new_password, user_inputs=user_data)

def _get_user_for_update_password(key, old_password):
	# verify old password
	if key:
		user = frappe.db.get_value("User", {"reset_password_key": key})
		if not user:
			return {
				'message': _("Cannot Update: Incorrect / Expired Link.")
			}

	elif old_password:
		# verify old password
		frappe.local.login_manager.check_password(frappe.session.user, old_password)
		user = frappe.session.user

	else:
		return

	return {
		'user': user
	}

def reset_user_data(user):
	user_doc = frappe.get_doc("User", user)
	redirect_url = user_doc.redirect_url
	user_doc.reset_password_key = ''
	user_doc.redirect_url = ''
	user_doc.save(ignore_permissions=True)

	return user_doc, redirect_url

@frappe.whitelist()
def verify_password(password):
	frappe.local.login_manager.check_password(frappe.session.user, password)

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
		user.flags.ignore_permissions = True
		user.insert()
		return _("Registration Details Emailed.")

@frappe.whitelist(allow_guest=True)
def reset_password(user):
	if user=="Administrator":
		return _("Not allowed to reset the password of {0}").format(user)

	try:
		user = frappe.get_doc("User", user)
		user.validate_reset_password()
		user.reset_password(send_email=True)

		return _("Password reset instructions have been sent to your email")

	except frappe.DoesNotExistError:
		return _("User {0} does not exist").format(user)

def user_query(doctype, txt, searchfield, start, page_len, filters):
	from frappe.desk.reportview import get_match_cond
	txt = "%{}%".format(txt)
	return frappe.db.sql("""select name, concat_ws(' ', first_name, middle_name, last_name)
		from `tabUser`
		where enabled=1
			and user_type = 'System User'
			and docstatus < 2
			and name not in ({standard_users})
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

def get_total_users():
	"""Returns total no. of system users"""
	return frappe.db.sql('''select sum(simultaneous_sessions) from `tabUser`
		where enabled=1 and user_type="System User"
		and name not in ({})'''.format(", ".join(["%s"]*len(STANDARD_USERS))), STANDARD_USERS)[0][0]

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
		and hour(timediff(now(), last_active)) < 72""".format(", ".join(["%s"]*len(STANDARD_USERS))), STANDARD_USERS)[0][0]

def get_website_users():
	"""Returns total no. of website users"""
	return frappe.db.sql("""select count(*) from `tabUser`
		where enabled = 1 and user_type = 'Website User'""")[0][0]

def get_active_website_users():
	"""Returns No. of website users who logged in, in the last 3 days"""
	return frappe.db.sql("""select count(*) from `tabUser`
		where enabled = 1 and user_type = 'Website User'
		and hour(timediff(now(), last_active)) < 72""")[0][0]

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

def notifify_admin_access_to_system_manager(login_manager=None):
	if (login_manager
		and login_manager.user == "Administrator"
		and frappe.local.conf.notifify_admin_access_to_system_manager):

		message = """<p>
			{dear_system_manager} <br><br>
			{access_message} <br><br>
			{is_it_unauthorized}
		</p>""".format(
			dear_system_manager=_("Dear System Manager,"),

			access_message=_("""Administrator accessed {0} on {1} via IP Address {2}.""").format(
				"""<a href="{site}" target="_blank">{site}</a>""".format(site=frappe.local.request.host_url),
				"""<b>{date_and_time}</b>""".format(date_and_time=format_datetime(now_datetime(), format_string="medium")),
				frappe.local.request_ip
			),

			is_it_unauthorized=_("If you think this is unauthorized, please change the Administrator password.")
		)

		frappe.sendmail(recipients=get_system_managers(), subject=_("Administrator Logged In"),
			message=message)

def extract_mentions(txt):
	"""Find all instances of @username in the string.
	The mentions will be separated by non-word characters or may appear at the start of the string"""
	return re.findall(r'(?:[^\w]|^)@([\w]*)', txt)
