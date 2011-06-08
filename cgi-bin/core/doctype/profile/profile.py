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

		self.doc.email = self.doc.email.strip()
		if self.doc.name not in ('Guest','Administrator'):
			if not validate_email_add(self.doc.email):
				msgprint("%s is not a valid email id" % self.doc.email)
				raise Exception
				self.doc.name = self.doc.email
	
	def on_update(self):
		# owner is always name
		if not self.doc.password:
			webnotes.conn.set(self.doc, 'password' ,'password')
		webnotes.conn.set(self.doc, 'owner' ,self.doc.name)


	def update_password(self):
		from webnotes.utils.email_lib import sendmail
		s
		sql("UPDATE `tabProfile` SET password=PASSWORD(%s) where name=%s", (self.doc.new_password, self.doc.name))
		email_text = '''%s,
		
Your password has been changed.
		
- Administrator
''' % self.doc.name
		sendmail([self.doc.email], subject='Change of Password Notification', parts = [('text/plain', email_text)])
		msgprint("Your password has been changed")
