# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class SocialLoginKey(Document):

	def autoname(self):
		self.name = frappe.scrub(self.provider_name)

	def after_insert(self):

		# Insert Username Field
		provider_username = frappe.new_doc("Custom Field")
		provider_username.dt = "User"
		provider_username.label = self.provider_name + " Username"
		provider_username.insert_after = "Third Party Authentication"
		provider_username.read_only = 1
		provider_username.hidden = 1
		provider_username.save()

		# Insert User ID Field
		provider_userid = frappe.new_doc("Custom Field")
		provider_userid.dt = "User"
		provider_userid.label = self.provider_name + " UserID"
		provider_userid.insert_after = "Third Party Authentication"
		provider_userid.read_only = 1
		provider_userid.hidden = 1
		provider_userid.save()

		# Change label to readable convention
		provider_userid.label = self.provider_name + " User ID"
		provider_userid.save()
		frappe.db.commit()

	def on_trash(self):

		# Delete Related Custom Fields on User DocType
		frappe.delete_doc("Custom Field", "User-"+frappe.scrub(self.provider_name + " Username"))
		frappe.delete_doc("Custom Field", "User-"+frappe.scrub(self.provider_name + " UserID"))
