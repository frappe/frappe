# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class Feedback(Document):
	pass

@frappe.whitelist(allow_guest=True)
def add_feedback(reference_doctype, reference_name, helpful):
	frappe.get_doc({
		"doctype": "Feedback",
		"reference_doctype": reference_doctype,
		"reference_name": reference_name,
		"helpful": helpful
	}).insert(ignore_permissions=True)

@frappe.whitelist()
def get_feedback_count(reference_name):

	return {
		"helpful": frappe.db.count("Feedback", {"reference_name": reference_name, "helpful": "Yes"}),
		"not_helpful": frappe.db.count("Feedback", {"reference_name": reference_name, "helpful": "No"}),
	}