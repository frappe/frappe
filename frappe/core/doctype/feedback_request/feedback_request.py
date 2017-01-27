# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class FeedbackRequest(Document):
	def before_insert(self):
		from frappe.utils import random_string

		self.key = random_string(32)

@frappe.whitelist(allow_guest=True)
def verify_feedback_request(key=None):
	if not key:
		return False

	is_feedback_submitted = frappe.db.get_value("Feedback Request", key, "is_feedback_submitted")
	if is_feedback_submitted:
		return True
	else:
		return False

def delete_feedback_request():
	""" clear 100 days old feedback request """
	frappe.db.sql("""delete `tabFeedback Request` where creation<DATE_SUB(NOW(), INTERVAL 100 DAY)""")