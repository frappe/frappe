# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
# import frappe
from frappe.model.document import Document

class test_template(Document):

	def db_insert(self):
		pass

	def load_from_db(self):
		pass

	def db_update(self):
		pass

	def get_list(self, args):
		pass

	pass