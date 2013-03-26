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

from __future__ import unicode_literals
import webnotes, json
from webnotes.utils import cint, now
from webnotes import _

class DocType:
	def __init__(self, doc, doclist):
		self.doc = doc
		self.doclist = doclist
		
	def autoname(self):
		"""set name as email id"""
		import re
		from webnotes.utils import validate_email_add

		if self.doc.name not in ('Guest','Administrator'):
			self.doc.email = self.doc.email.strip()
			if not validate_email_add(self.doc.email):
				webnotes.msgprint("%s is not a valid email id" % self.doc.email)
				raise Exception
		
			self.doc.name = self.doc.email

	def validate(self):
		self.in_insert = self.doc.fields.get("__islocal")
		self.validate_max_users()
		self.check_one_system_manager()
		self.check_enable_disable()

		if self.doc.fields.get('__islocal') and not self.doc.new_password:
			webnotes.msgprint("Password required while creating new doc", raise_exception=1)

	def check_enable_disable(self):
		# do not allow disabling administrator/guest
		if not cint(self.doc.enabled) and self.doc.name in ["Administrator", "Guest"]:
			webnotes.msgprint("Hey! You cannot disable user: %s" % self.doc.name,
				raise_exception=1)
		
		# clear sessions if disabled
		if not cint(self.doc.enabled) and getattr(webnotes, "login_manager", None):
			webnotes.login_manager.logout(user=self.doc.name)
		
	def validate_max_users(self):
		"""don't allow more than max users if set in conf"""
		import conf
		# check only when enabling a user
		if hasattr(conf, 'max_users') and self.doc.enabled and \
				self.doc.name not in ["Administrator", "Guest"]:
			active_users = webnotes.conn.sql("""select count(*) from tabProfile
				where ifnull(enabled, 0)=1 and docstatus<2
				and name not in ('Administrator', 'Guest', %s)""", (self.doc.name,))[0][0]
			if active_users >= conf.max_users and conf.max_users:
				webnotes.msgprint("""
					You already have <b>%(active_users)s</b> active users, \
					which is the maximum number that you are currently allowed to add. <br /><br /> \
					So, to add more users, you can:<br /> \
					1. <b>Upgrade to the unlimited users plan</b>, or<br /> \
					2. <b>Disable one or more of your existing users and try again</b>""" \
					% {'active_users': active_users}, raise_exception=1)
						
	def check_one_system_manager(self):
		# if adding system manager, do nothing
		if not cint(self.doc.enabled) or ("System Manager" in [user_role.role for user_role in
				self.doclist.get({"parentfield": "user_roles"})]):
			return
		
		if not webnotes.conn.sql("""select distinct parent from tabUserRole user_role
				where role='System Manager' and docstatus<2 
				and parent not in ('Administrator', %s) and exists 
					(select * from `tabProfile` profile 
					where profile.name=user_role.parent and enabled=1)""", (self.doc.name,)):
			webnotes.msgprint("""Adding System Manager Role as there must 
				be atleast one 'System Manager'.""")
			self.doclist.append({
				"doctype": "UserRole",
				"parentfield": "user_roles",
				"role": "System Manager"
			})
				
	def on_update(self):
		# owner is always name
		webnotes.conn.set(self.doc, 'owner', self.doc.name)
		self.update_new_password()

	def update_new_password(self):
		"""update new password if set"""
		if self.doc.new_password:
			from webnotes.auth import update_password
			update_password(self.doc.name, self.doc.new_password)
			
			if self.in_insert:
				webnotes.msgprint("New user created. - %s" % self.doc.name)
				if cint(self.doc.send_invite_email):
					webnotes.msgprint("Sent welcome mail.")
					self.send_welcome_mail(self.doc.new_password)
			else:
				self.password_reset_mail(self.doc.new_password)
				webnotes.msgprint("Password updated.")
				
			webnotes.conn.set(self.doc, 'new_password', '')

	def get_fullname(self):
		"""get first_name space last_name"""
		return (self.doc.first_name or '') + \
			(self.doc.first_name and " " or '') + (self.doc.last_name or '')

	def password_reset_mail(self, password):
		"""reset password"""
		txt = """
## Password Reset

Dear %(first_name)s,

Your password has been reset. Your new password is:

password: %(password)s

To login to %(product)s, please go to:

%(login_url)s

Thank you,<br>
%(user_fullname)s
		"""
		self.send_login_mail("Your ERPNext password has been reset", txt, password)
		
	def send_welcome_mail(self, password):
		"""send welcome mail to user with password and login url"""
		import startup
		
		txt = """
## %(company)s

Dear %(first_name)s,

A new account has been created for you, here are your details:

Login Id: %(user)s<br>
Password: %(password)s

To login to your new %(product)s account, please go to:

%(login_url)s

Thank you,<br>
%(user_fullname)s
		"""
		self.send_login_mail("Welcome to " + startup.product_name, txt, password)

	def send_login_mail(self, subject, txt, password):
		"""send mail with login details"""
		import os
	
		import startup
		from webnotes.utils.email_lib import sendmail_md
		from webnotes.profile import get_user_fullname
		from webnotes.utils import get_request_site_address
	
		args = {
			'first_name': self.doc.first_name or self.doc.last_name or "user",
			'user': self.doc.name,
			'password': password,
			'company': webnotes.conn.get_default('company') or startup.product_name,
			'login_url': get_request_site_address(),
			'product': startup.product_name,
			'user_fullname': get_user_fullname(webnotes.session['user'])
		}
		sendmail_md(self.doc.email, subject=subject, msg=txt % args)
		
	def on_trash(self):
		if self.doc.name in ["Administrator", "Guest"]:
			webnotes.msgprint("""Hey! You cannot delete user: %s""" % (self.name, ),
				raise_exception=1)
				
		# disable the user and log him/her out
		self.doc.enabled = 0
		if getattr(webnotes, "login_manager"):
			webnotes.login_manager.logout(user=self.doc.name)
		
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
	
	def on_rename(self,newdn,olddn):
		# do not allow renaming administrator and guest
		if olddn in ["Administrator", "Guest"]:
			webnotes.msgprint("""Hey! You are restricted from renaming the user: %s""" % \
				(olddn, ), raise_exception=1)
			
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
		webnotes.conn.sql("""update __Auth set user=%s where user=%s""", (newdn, olddn))
						
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

@webnotes.whitelist()
def update_profile(fullname, password=None):
	if not fullname:
		return _("Name is required")
	
	webnotes.conn.set_value("Profile", webnotes.session.user, "first_name", fullname)
	webnotes.add_cookies["full_name"] = fullname
		
	if password:
		from webnotes.auth import update_password
		update_password(webnotes.session.user, password)

	return _("Updated")
	
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
			"user_type": "Partner",
			"send_invite_email": 1
		})
		profile.ignore_permissions = True
		profile.insert()
		return _("Registration Details Emailed.")
				