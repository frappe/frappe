# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import validate_email_add


class Domain(Document):
	def autoname(self):
		if self.domain_name:
			self.name = self.domain_name

	def validate(self):
		"""Validate email id and check POP3/IMAP and SMTP connections is enabled."""
		if self.email_id:
			validate_email_add(self.email_id, True)

		if frappe.local.flags.in_patch or frappe.local.flags.in_test:
			return

		if not frappe.local.flags.in_install and not frappe.local.flags.in_patch:
			email_account = frappe.get_doc({
				"doctype": "Email Account",
				"email_server": self.email_server,
				"email_id": self.email_id,
				"password": self.password,
				"enable_incoming":1,
				"use_ssl": self.use_ssl,
				"use_imap": self.use_imap,
				"enable_outgoing":1,
				"use_tls":self.use_tls,
				"smtp_server":self.smtp_server,
				"smtp_port":self.smtp_port
			})
			email_account.get_server()
			email_account.check_smtp()

	def on_update(self):
		"""update all email accounts using this domain"""
		for email_account in frappe.get_all("Email Account",
		filters={"domain": self.name}):

			email_account = frappe.get_doc("Email Account",
				email_account.name)
			email_account.set("email_server",self.email_server)
			email_account.set("use_imap",self.use_imap)
			email_account.set("use_ssl",self.use_ssl)
			email_account.set("use_tls",self.use_tls)
			email_account.set("attachment_limit",self.attachment_limit)
			email_account.set("smtp_server",self.smtp_server)
			email_account.set("smtp_port",self.smtp_port)
			email_account.save()

