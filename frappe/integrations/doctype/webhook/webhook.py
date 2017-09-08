# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document

class Webhook(Document):
	def autoname(self):
		if self.webhook_type == "Scheduler Event" and self.scheduler_event:
			self.name = self.webhook_type + "-" + self.scheduler_event
		if self.webhook_type == "Doc Event" and self.webhook_doctype:
			self.name = self.webhook_type + "-" + self.webhook_doctype + "-" + self.webhook_docevent
	def validate(self):
		self.validate_mandatory_fields()
		self.validate_docevent()
	def validate_mandatory_fields(self):
		if self.webhook_type == "Scheduler Event":
			if not self.scheduler_event:
				frappe.throw(_("Select Scheduler Event"))
		if self.webhook_type == "Doc Event":
			if not self.webhook_doctype:
				frappe.throw(_("Select DocType"))
	def validate_docevent(self):
		if self.doctype:
			is_submittable = frappe.get_value("DocType", self.doctype, "is_submittable")
			if not is_submittable and self.webhook_docevent in ["on_submit", "on_cancel", "on_update_after_submit"]:
				frappe.throw(_("DocType must be Submittable for the selected Doc Event"))
