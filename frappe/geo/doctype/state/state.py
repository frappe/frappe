# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class State(Document):
	def autoname(self):
		country_code = frappe.db.get_value("Country", self.country, "code").upper()
		self.name = "{state} - {country_code}".format(state=self.state, country_code=country_code)
