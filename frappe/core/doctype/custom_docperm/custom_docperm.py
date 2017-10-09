# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class CustomDocPerm(Document):
	def before_save(self):
		doctype = self.parent_doctype or self.parent
		self.parent = doctype
		self.parent_doctype = doctype
