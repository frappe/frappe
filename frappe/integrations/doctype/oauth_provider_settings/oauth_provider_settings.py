# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _

class OAuthProviderSettings(Document):
	pass

def get_oauth_settings():
	"""Returns oauth settings"""
	out = frappe._dict({
		"skip_authorization" : frappe.db.get_value("OAuth Provider Settings", None, "skip_authorization")
	})

	return out