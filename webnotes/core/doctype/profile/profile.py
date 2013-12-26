# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import webnotes, json
from webnotes.utils import cint, now, cstr
from webnotes import _

class DocType:
	def __init__(self, doc, doclist):
		self.doc = doc
		self.doclist = doclist
		
	def autoname(self):
		"""set name as email id"""
		if self.doc.name not in ('Guest','Administrator'):
			self.doc.email = self.doc.email.strip()		
			self.doc.name = self.doc.email
			
			if webnotes.conn.exists("Profile", self.doc.name):
				webnotes.msgprint("Name Exists", raise_exception=True)

	def validate(self):
		self.in_insert = self.doc.fields.get("__islocal")
		if self.doc.name not in ('Guest','Administrator'):
			self.validate_email_type(self.doc.email)
		self.validate_max_users()
		self.add_system_manager_role()
		self.check_enable_disable()
		if self.in_insert:
			if self.doc.name not in ("Guest", "Administrator"):
				self.send_welcome_mail()
				webnotes.msgprint(_("Welcome Email Sent"))
		else:
			self.email_new_password()

		self.doc.new_password = ""

	def check_enable_disable(self):
		# do not allow disabling administrator/guest
		if not cint(self.doc.enabled) and self.doc.name in ["Administrator", "Guest"]:
			webnotes.msgprint("Hey! You cannot disable user: %s" % self.doc.name,
				raise_exception=1)
				
		if not cint(self.doc.enabled):
			self.a_system_manager_should_exist()
		
		# clear sessions if disabled
		if not cint(self.doc.enabled) and getattr(webnotes, "login_manager", None):
			webnotes.local.login_manager.logout(user=self.doc.name)
		
	def validate_max_users(self):
		"""don't allow more than max users if set in conf"""
		from webnotes import conf
		# check only when enabling a user
		if 'max_users' in conf and self.doc.enabled and \
				self.doc.name not in ["Administrator", "Guest"] and \
				cstr(self.doc.user_type).strip() in ("", "System User"):
			active_users = webnotes.conn.sql("""select count(*) from tabProfile
				where ifnull(enabled, 0)=1 and docstatus<2
				and ifnull(user_type, "System User") = "System User"
				and name not in ('Administrator', 'Guest', %s)""", (self.doc.name,))[0][0]
			if active_users >= conf.max_users and conf.max_users:
				webnotes.msgprint("""
					You already have <b>%(active_users)s</b> active users, \
					which is the maximum number that you are currently allowed to add. <br /><br /> \
					So, to add more users, you can:<br /> \
					1. <b>Upgrade to the unlimited users plan</b>, or<br /> \
					2. <b>Disable one or more of your existing users and try again</b>""" \
					% {'active_users': active_users}, raise_exception=1)
						
	def add_system_manager_role(self):
		# if adding system manager, do nothing
		if not cint(self.doc.enabled) or ("System Manager" in [user_role.role for user_role in
				self.doclist.get({"parentfield": "user_roles"})]):
			return
		
		if self.doc.user_type == "System User" and not self.get_other_system_managers():
			webnotes.msgprint("""Adding System Manager Role as there must 
				be atleast one 'System Manager'.""")
			self.doclist.append({
				"doctype": "UserRole",
				"parentfield": "user_roles",
				"role": "System Manager"
			})
	
	def email_new_password(self):
		if self.doc.new_password and not self.in_insert:
			from webnotes.auth import _update_password
			_update_password(self.doc.name, self.doc.new_password)

			self.password_update_mail(self.doc.new_password)
			webnotes.msgprint("New Password Emailed.")
			
	def on_update(self):
		# owner is always name
		webnotes.conn.set(self.doc, 'owner', self.doc.name)
		webnotes.clear_cache(user=self.doc.name)
	
	def reset_password(self):
		from webnotes.utils import random_string, get_url

		key = random_string(32)
		webnotes.conn.set_value("Profile", self.doc.name, "reset_password_key", key)
		self.password_reset_mail(get_url("/update-password?key=" + key))
	
	def get_other_system_managers(self):
		return webnotes.conn.sql("""select distinct parent from tabUserRole user_role
			where role='System Manager' and docstatus<2
			and parent not in ('Administrator', %s) and exists 
				(select * from `tabProfile` profile 
				where profile.name=user_role.parent and enabled=1)""", (self.doc.name,))

	def get_fullname(self):
		"""get first_name space last_name"""
		return (self.doc.first_name or '') + \
			(self.doc.first_name and " " or '') + (self.doc.last_name or '')

	def password_reset_mail(self, link):
		"""reset password"""
		txt = """
## Password Reset

Dear %(first_name)s,

Please click on the following link to update your new password:

<a href="%(link)s">%(link)s</a>

Thank you,<br>
%(user_fullname)s
		"""
		self.send_login_mail("Password Reset", 
			txt, {"link": link})
	
	def password_update_mail(self, password):
		txt = """
## Password Update Notification

Dear %(first_name)s,

Your password has been updated. Here is your new password: %(new_password)s

Thank you,<br>
%(user_fullname)s
		"""
		self.send_login_mail("Password Update", 
			txt, {"new_password": password})
		

	def send_welcome_mail(self):
		"""send welcome mail to user with password and login url"""

		from webnotes.utils import random_string, get_url

		self.doc.reset_password_key = random_string(32)
		link = get_url("/update-password?key=" + self.doc.reset_password_key)
		
		txt = """
## %(company)s

Dear %(first_name)s,

A new account has been created for you. 

Your login id is: %(user)s

To complete your registration, please click on the link below:

<a href="%(link)s">%(link)s</a>

Thank you,<br>
%(user_fullname)s
		"""
		self.send_login_mail("New Account", txt, 
			{ "link": link })

	def send_login_mail(self, subject, txt, add_args):
		"""send mail with login details"""
		import os
	
		from webnotes.utils.email_lib import sendmail_md
		from webnotes.profile import get_user_fullname
		from webnotes.utils import get_url
		
		full_name = get_user_fullname(webnotes.session['user'])
		if full_name == "Guest":
			full_name = "Administrator"
	
		args = {
			'first_name': self.doc.first_name or self.doc.last_name or "user",
			'user': self.doc.name,
			'company': webnotes.conn.get_default('company'),
			'login_url': get_url(),
			'user_fullname': full_name
		}
		
		args.update(add_args)
		
		sender = webnotes.session.user not in ("Administrator", "Guest") and webnotes.session.user or None
		
		sendmail_md(recipients=self.doc.email, sender=sender, subject=subject, msg=txt % args)
		
	def a_system_manager_should_exist(self):
		if not self.get_other_system_managers():
			webnotes.msgprint(_("""Hey! There should remain at least one System Manager"""),
				raise_exception=True)
		
	def on_trash(self):
		webnotes.clear_cache(user=self.doc.name)
		if self.doc.name in ["Administrator", "Guest"]:
			webnotes.msgprint("""Hey! You cannot delete user: %s""" % (self.name, ),
				raise_exception=1)
		
		self.a_system_manager_should_exist()
				
		# disable the user and log him/her out
		self.doc.enabled = 0
		if getattr(webnotes.local, "login_manager", None):
			webnotes.local.login_manager.logout(user=self.doc.name)
		
		# delete their password
		webnotes.conn.sql("""delete from __Auth where user=%s""", self.doc.name)
		
		# delete todos
		webnotes.conn.sql("""delete from `tabToDo` where owner=%s""", self.doc.name)
		webnotes.conn.sql("""update tabToDo set assigned_by=null where assigned_by=%s""",
			self.doc.name)
		
		# delete events
		webnotes.conn.sql("""delete from `tabEvent` where owner=%s
			and event_type='Private'""", self.doc.name)
		webnotes.conn.sql("""delete from `tabEvent User` where person=%s""", self.doc.name)
			
		# delete messages
		webnotes.conn.sql("""delete from `tabComment` where comment_doctype='Message'
			and (comment_docname=%s or owner=%s)""", (self.doc.name, self.doc.name))
			
	def before_rename(self, olddn, newdn, merge=False):
		webnotes.clear_cache(user=olddn)
		self.validate_rename(olddn, newdn)
	
	def validate_rename(self, olddn, newdn):
		# do not allow renaming administrator and guest
		if olddn in ["Administrator", "Guest"]:
			webnotes.msgprint("""Hey! You are restricted from renaming the user: %s""" % \
				(olddn, ), raise_exception=1)
		
		self.validate_email_type(newdn)
	
	def validate_email_type(self, email):
		from webnotes.utils import validate_email_add
	
		email = email.strip()
		if not validate_email_add(email):
			webnotes.msgprint("%s is not a valid email id" % email)
			raise Exception
	
	def after_rename(self, olddn, newdn, merge=False):			
		tables = webnotes.conn.sql("show tables")
		for tab in tables:
			desc = webnotes.conn.sql("desc `%s`" % tab[0], as_dict=1)
			has_fields = []
			for d in desc:
				if d.get('Field') in ['owner', 'modified_by']:
					has_fields.append(d.get('Field'))
			for field in has_fields:
				webnotes.conn.sql("""\
					update `%s` set `%s`=%s
					where `%s`=%s""" % \
					(tab[0], field, '%s', field, '%s'), (newdn, olddn))
					
		# set email
		webnotes.conn.sql("""\
			update `tabProfile` set email=%s
			where name=%s""", (newdn, newdn))
		
		# update __Auth table
		if not merge:
			webnotes.conn.sql("""update __Auth set user=%s where user=%s""", (newdn, olddn))
			
	def add_roles(self, *roles):
		for role in roles:
			if role in [d.role for d in self.doclist.get({"doctype":"UserRole"})]:
				continue
			self.bean.doclist.append({
				"doctype": "UserRole",
				"parentfield": "user_roles",
				"role": role
			})
			
		self.bean.save()

@webnotes.whitelist()
def get_languages():
	from webnotes.translate import get_lang_dict
	languages = get_lang_dict().keys()
	languages.sort()
	return [""] + languages

@webnotes.whitelist()
def get_all_roles(arg=None):
	"""return all roles"""
	return [r[0] for r in webnotes.conn.sql("""select name from tabRole
		where name not in ('Administrator', 'Guest', 'All') order by name""")]
		
@webnotes.whitelist()
def get_user_roles(arg=None):
	"""get roles for a user"""
	return webnotes.get_roles(webnotes.form_dict['uid'])

@webnotes.whitelist()
def get_perm_info(arg=None):
	"""get permission info"""
	return webnotes.conn.sql("""select parent, permlevel, `read`, `write`, submit,
		cancel, amend from tabDocPerm where role=%s 
		and docstatus<2 order by parent, permlevel""", 
			webnotes.form_dict['role'], as_dict=1)

@webnotes.whitelist(allow_guest=True)
def update_password(new_password, key=None, old_password=None):
	# verify old password
	if key:
		user = webnotes.conn.get_value("Profile", {"reset_password_key":key})
		if not user:
			return _("Cannot Update: Incorrect / Expired Link.")
	elif old_password:
		user = webnotes.session.user
		if not webnotes.conn.sql("""select user from __Auth where password=password(%s) 
			and user=%s""", (old_password, user)):
			return _("Cannot Update: Incorrect Password")
	
	from webnotes.auth import _update_password
	_update_password(user, new_password)
	
	webnotes.conn.set_value("Profile", user, "reset_password_key", "")
	
	return _("Password Updated")
	
@webnotes.whitelist(allow_guest=True)
def sign_up(email, full_name):
	profile = webnotes.conn.get("Profile", {"email": email})
	if profile:
		if profile.disabled:
			return _("Registered but disabled.")
		else:
			return _("Already Registered")
	else:
		if webnotes.conn.sql("""select count(*) from tabProfile where 
			TIMEDIFF(%s, modified) > '1:00:00' """, now())[0][0] > 200:
			raise Exception, "Too Many New Profiles"
		from webnotes.utils import random_string
		profile = webnotes.bean({
			"doctype":"Profile",
			"email": email,
			"first_name": full_name,
			"enabled": 1,
			"new_password": random_string(10),
			"user_type": "Website User"
		})
		profile.ignore_permissions = True
		profile.insert()
		return _("Registration Details Emailed.")

@webnotes.whitelist(allow_guest=True)
def reset_password(user):	
	user = webnotes.form_dict.get('user', '')
	if user in ["demo@erpnext.com", "Administrator"]:
		return "Not allowed"
		
	if webnotes.conn.sql("""select name from tabProfile where name=%s""", user):
		# Hack!
		webnotes.session["user"] = "Administrator"
		profile = webnotes.bean("Profile", user)
		profile.get_controller().reset_password()
		return "Password reset details sent to your email."
	else:
		return "No such user (%s)" % user

def profile_query(doctype, txt, searchfield, start, page_len, filters):
	from webnotes.widgets.reportview import get_match_cond
	return webnotes.conn.sql("""select name, concat_ws(' ', first_name, middle_name, last_name) 
		from `tabProfile` 
		where ifnull(enabled, 0)=1 
			and docstatus < 2 
			and name not in ('Administrator', 'Guest') 
			and user_type != 'Website User'
			and (%(key)s like "%(txt)s" 
				or concat_ws(' ', first_name, middle_name, last_name) like "%(txt)s") 
			%(mcond)s
		order by 
			case when name like "%(txt)s" then 0 else 1 end, 
			case when concat_ws(' ', first_name, middle_name, last_name) like "%(txt)s" 
				then 0 else 1 end, 
			name asc 
		limit %(start)s, %(page_len)s""" % {'key': searchfield, 'txt': "%%%s%%" % txt,  
		'mcond':get_match_cond(doctype, searchfield), 'start': start, 'page_len': page_len})

def get_total_users():
	"""Returns total no. of system users"""
	return webnotes.conn.sql("""select count(*) from `tabProfile`
		where enabled = 1 and user_type != 'Website User'
		and name not in ('Administrator', 'Guest')""")[0][0]

def get_active_users():
	"""Returns No. of system users who logged in, in the last 3 days"""
	return webnotes.conn.sql("""select count(*) from `tabProfile`
		where enabled = 1 and user_type != 'Website User'
		and name not in ('Administrator', 'Guest')
		and hour(timediff(now(), last_login)) < 72""")[0][0]

def get_website_users():
	"""Returns total no. of website users"""
	return webnotes.conn.sql("""select count(*) from `tabProfile`
		where enabled = 1 and user_type = 'Website User'""")[0][0]
	
def get_active_website_users():
	"""Returns No. of website users who logged in, in the last 3 days"""
	return webnotes.conn.sql("""select count(*) from `tabProfile`
		where enabled = 1 and user_type = 'Website User'
		and hour(timediff(now(), last_login)) < 72""")[0][0]

