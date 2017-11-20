# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, os
from frappe.model.document import Document
from frappe.modules.utils import export_module_json

class SocialLoginKey(Document):

	def autoname(self):
		self.name = frappe.scrub(self.provider_name)

	def after_insert(self):
		if not frappe.db.exists("Custom Field", "User-"+frappe.scrub(self.provider_name + " Username")):
			self.create_username_custom_field()
		if not frappe.db.exists("Custom Field", "User-"+frappe.scrub(self.provider_name + " UserID")):
			self.create_userid_custom_field()

	def on_trash(self):

		# Delete Related Custom Fields on User DocType
		frappe.delete_doc("Custom Field", "User-"+frappe.scrub(self.provider_name + " Username"))
		frappe.delete_doc("Custom Field", "User-"+frappe.scrub(self.provider_name + " UserID"))

	def create_username_custom_field(self):
		# Insert Username Field
		provider_username = frappe.new_doc("Custom Field")
		provider_username.dt = "User"
		provider_username.label = self.provider_name + " Username"
		provider_username.insert_after = "Third Party Authentication"
		provider_username.read_only = 1
		provider_username.hidden = 1
		provider_username.save()
		frappe.db.commit()

	def create_userid_custom_field(self):
		# Insert User ID Field
		provider_userid = frappe.new_doc("Custom Field")
		provider_userid.dt = "User"
		provider_userid.label = self.provider_name + " UserID"
		provider_userid.insert_after = "Third Party Authentication"
		provider_userid.read_only = 1
		provider_userid.hidden = 1
		provider_userid.save()
		frappe.db.commit()

		# Change label to readable convention
		provider_userid.label = self.provider_name + " User ID"
		provider_userid.save()
		frappe.db.commit()

	def on_update(self):
		"""
			Writes the .py login_via_provider endpoint
		"""
		module = frappe.db.get_value('DocType', self.doctype, 'module')
		if frappe.conf.developer_mode:
			path = export_module_json(self, not self.custom, module)
		else :
			path = None
		py_file = "from __future__ import unicode_literals\n"
		py_file += "import frappe\n"
		py_file += "from frappe.utils.oauth import login_via_oauth2\n\n"
		py_file += "@frappe.whitelist(allow_guest=True)\n"
		py_file += "def login_via_" + self.name + "(code, state):\n"
		py_file += "\tlogin_via_oauth2(\"" + self.name + "\", code, state)"
		if path:
			# py
			if not os.path.exists(path + '.py'):
				with open(path + '.py', 'w') as f:
					f.write(py_file)
				self.redirect_url = "/api/method/frappe.integrations.social_login_key."
				self.redirect_url += self.name + "." + self.name + "." + "login_via_" + self.name