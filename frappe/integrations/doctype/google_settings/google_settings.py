# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
# import frappe
from frappe.model.document import Document

class GoogleSettings(Document):
	pass

def get_auth_url():
	return "https://www.googleapis.com/oauth2/v4/token"