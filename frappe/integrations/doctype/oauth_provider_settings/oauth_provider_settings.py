# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _

class OAuthProviderSettings(Document):

	
	def validate(self):
		self.provider_url = self.protocol + "://" + self.site_address


def get_oauth_settings():
	"""Returns oauth settings"""
	out = frappe._dict({
		"provider_url" : frappe.db.get_value("OAuth Provider Settings", None, "provider_url"),
		"skip_authorization" : frappe.db.get_value("OAuth Provider Settings", None, "skip_authorization")
	})

	if not out["provider_url"]:
		frappe.throw(_("Please set the Provider URL in OAuth Provider Settings"))

	return out