# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.model.document import Document
import frappe.cache_manager

class MilestoneTracker(Document):
	def on_update(self):
		frappe.cache_manager.clear_doctype_map('Milestone Tracker', self.name)

	def on_trash(self):
		frappe.cache_manager.clear_doctype_map('Milestone Tracker', self.name)

	def apply(self, doc):
		before_save = doc.get_doc_before_save()
		from_value = before_save and before_save.get(self.track_field) or None
		if from_value != doc.get(self.track_field):
			frappe.get_doc(dict(
				doctype = 'Milestone',
				reference_type = doc.doctype,
				reference_name = doc.name,
				track_field = self.track_field,
				from_value = from_value,
				value = doc.get(self.track_field),
				milestone_tracker = self.name,
			)).insert(ignore_permissions=True)

def evaluate_milestone(doc, event):
	if (frappe.flags.in_install
		or frappe.flags.in_migrate
		or frappe.flags.in_setup_wizard):
		return
	for d in frappe.cache_manager.get_doctype_map('Milestone Tracker', doc.doctype,
		dict(document_type = doc.doctype, disabled=0)):
		frappe.get_doc('Milestone Tracker', d.name).apply(doc)
