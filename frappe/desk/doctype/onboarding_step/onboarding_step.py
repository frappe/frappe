# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document

class OnboardingStep(Document):
	def before_export(self, doc):
		doc.is_complete = 0
		doc.is_skipped = 0
