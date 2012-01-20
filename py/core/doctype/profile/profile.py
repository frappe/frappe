# Please edit this list and import only required elements
import webnotes

from webnotes import msgprint

sql = webnotes.conn.sql
	
# -----------------------------------------------------------------------------------------

	
class DocType:
	def __init__(self, doc, doclist):
		self.doc = doc
		self.doclist = doclist
	
	# Autoname is Email id
	# --------------------

	def autoname(self):
		import re
		from webnotes.utils import validate_email_add

		if self.doc.name not in ('Guest','Administrator'):
			self.doc.email = self.doc.email.strip()
			if not validate_email_add(self.doc.email):
				msgprint("%s is not a valid email id" % self.doc.email)
				raise Exception
		
			self.doc.name = self.doc.email
	
	def on_update(self):
		# owner is always name
		if not self.doc.password:
			webnotes.conn.set(self.doc, 'password' ,'password')
		webnotes.conn.set(self.doc, 'owner' ,self.doc.name)

	def get_fullname(self):
		return (self.doc.first_name or '') + \
			(self.doc.first_name and " " or '') + (self.doc.last_name or '')
		
	def reset_password(self):
		"""reset password"""
		from webnotes.utils import random_string, now
		import os
		pwd = random_string(8)
		
		# update tab Profile
		webnotes.conn.sql("""UPDATE tabProfile SET password=password(%s), modified=%s 
			WHERE name=%s""", (pwd, now(), self.doc.name))

		# send email
		with open(os.path.join(os.path.dirname(__file__), 'password_reset.txt'), 'r') as f:
			reset_password_mail = f.read()

		
		from webnotes.utils.email_lib import sendmail_md
		sendmail_md(recipients= self.doc.email or self.doc.name, \
			msg = reset_password_mail % {"user": self.get_fullname(), "password":pwd}, \
			subject = 'Password Reset')
			