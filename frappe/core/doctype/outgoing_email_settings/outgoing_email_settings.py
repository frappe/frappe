# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _, throw
from frappe.utils import validate_email_add
from frappe.model.document import Document

class OutgoingEmailSettings(Document):

	def validate(self):
		if self.auto_email_id and not validate_email_add(self.auto_email_id):
			throw(_("{0} is not a valid email id").format(self.auto_email_id), frappe.InvalidEmailAddressError)

		if self.mail_server and not frappe.local.flags.in_patch:
			from frappe.utils import cint
			from frappe.utils.email_lib.smtp import SMTPServer
			smtpserver = SMTPServer(login = self.mail_login,
				password = self.mail_password,
				server = self.mail_server,
				port = cint(self.mail_port),
				use_ssl = cint(self.use_ssl)
			)

			# exceptions are handled in session connect
			sess = smtpserver.sess

def get_mail_footer():
	return frappe.db.get_value("Outgoing Email Settings", "Outgoing Email Settings", "footer") or ""
