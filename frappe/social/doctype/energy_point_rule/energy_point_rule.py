# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
import frappe.cache_manager
from frappe.model.document import Document
from frappe.social.doctype.energy_point_settings.energy_point_settings import is_energy_point_enabled
from frappe.social.doctype.energy_point_log.energy_point_log import create_energy_points_log, revert

class EnergyPointRule(Document):
	def on_update(self):
		frappe.cache_manager.clear_doctype_map('Energy Point Rule', self.name)

	def on_trash(self):
		frappe.cache_manager.clear_doctype_map('Energy Point Rule', self.name)

	def apply(self, doc):
		if self.rule_condition_satisfied(doc):
			multiplier = 1

			points = self.points
			if self.multiplier_field:
				multiplier = doc.get(self.multiplier_field) or 1
				points = round(points * multiplier)
				max_points = self.max_points
				if max_points and points > max_points:
					points = max_points

			reference_doctype = doc.doctype
			reference_name = doc.name
			user = doc.get(self.user_field)
			rule = self.name

			# incase of zero as result after roundoff
			if not points: return

			# if user_field has no value
			if not user or user == 'Administrator': return

			try:
				create_energy_points_log(reference_doctype, reference_name, {
					'points': points,
					'user': user,
					'rule': rule
				})
			except Exception as e:
				frappe.log_error(frappe.get_traceback(), 'apply_energy_point')

	def rule_condition_satisfied(self, doc):
		if self.for_doc_event == 'New':
			# indicates that this was a new doc
			return doc.get_doc_before_save() == None
		if self.for_doc_event == 'Submit':
			return doc.docstatus == 1
		if self.for_doc_event == 'Cancel':
			return doc.docstatus == 2
		if self.for_doc_event == 'Custom' and self.condition:
			return frappe.safe_eval(self.condition, None, {'doc': doc.as_dict()})
		return False

def process_energy_points(doc, state):
	if (frappe.flags.in_patch
		or frappe.flags.in_install
		or not is_energy_point_enabled()):
		return

	old_doc = doc.get_doc_before_save()

	# check if doc has been cancelled
	if old_doc and old_doc.docstatus == 1 and doc.docstatus == 2:
		return revert_points_for_cancelled_doc(doc)

	for d in frappe.cache_manager.get_doctype_map('Energy Point Rule', doc.doctype,
		dict(reference_doctype = doc.doctype, enabled=1)):
		frappe.get_doc('Energy Point Rule', d.get('name')).apply(doc)


def revert_points_for_cancelled_doc(doc):
	energy_point_logs = frappe.get_all('Energy Point Log', {
		'reference_doctype': doc.doctype,
		'reference_name': doc.name,
		'type': 'Auto'
	})
	for log in energy_point_logs:
		revert(log.name, _('Reference document has been cancelled'))


def get_energy_point_doctypes():
	return [
		d.reference_doctype for d in frappe.get_all('Energy Point Rule',
			['reference_doctype'], {'enabled': 1})
	]
