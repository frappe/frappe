# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.frappeclient import FrappeClient
from frappe.model.document import Document

class Node(Document):
	def before_insert(self):
		self.api_key = frappe.generate_hash(length = 15)
		self.api_secret = frappe.generate_hash(length = 15)
