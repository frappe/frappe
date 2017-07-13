# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class DomainSettings(Document):
	def on_update(self):
		cache = frappe.cache()
		cache.delete_key("domains", "active_domains")
		cache.delete_key("modules", "active_modules")