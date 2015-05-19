# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _

class EmailUnsubscribe(Document):
	def on_update(self):
		doc = frappe.get_doc(self.reference_doctype, self.reference_name)
		doc.add_comment("Label", _("Left this conversation"), comment_by=self.email)
