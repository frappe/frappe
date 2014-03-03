# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
	def validate(self):
		self.doc.encode()
		if self.doc.mail_server:
			from frappe.utils import cint
			from frappe.utils.email_lib.smtp import SMTPServer
			smtpserver = SMTPServer(login = self.doc.mail_login,
				password = self.doc.mail_password,
				server = self.doc.mail_server,
				port = cint(self.doc.mail_port),
				use_ssl = self.doc.use_ssl
			)
						
			# exceptions are handled in session connect
			sess = smtpserver.sess