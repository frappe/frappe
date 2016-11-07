# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

from frappe.model.document import Document
from frappe import _

class SocialLoginKeys(Document):
	def validate(self):
		self.validate_frappe_server_url()

	def validate_frappe_server_url(self):
		if self.frappe_server_url:
			if self.frappe_server_url.endswith('/'):
				self.frappe_server_url = self.frappe_server_url[:-1]
			import requests
			try:
				r = requests.get(self.frappe_server_url + "/api/method/frappe.handler.version", timeout=5)
			except:
				frappe.throw(_("Unable to make request to the Frappe Server URL"))
			if r.status_code != 200:
				frappe.throw(_("Check Frappe Server URL"))
