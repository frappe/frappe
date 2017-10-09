# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from frappe import _
from frappe.model.document import Document
import frappe

class ActivityLog(Document):
	def on_trash(self): # pylint: disable=no-self-use
		frappe.throw(_("Sorry! You cannot delete auto-generated comments"))