# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import frappe.cache_manager
from frappe.model.document import Document
from frappe.social.doctype.energy_point_settings.energy_point_settings import is_energy_point_enabled
from frappe.social.doctype.energy_point_log.energy_point_log import create_energy_points_log

class EnergyPointRule(Document):
	def on_update(self):
		frappe.cache_manager.clear_doctype_map('Energy Point Rule', self.name)

	def on_trash(self):
		frappe.cache_manager.clear_doctype_map('Energy Point Rule', self.name)

	def apply(self, doc):
		if frappe.safe_eval(self.condition, None, {'doc': doc.as_dict()}):
			multiplier = 1

			if self.multiplier_field:
				multiplier = doc.get(self.multiplier_field) or 1

			points = round(self.points * multiplier)
			reference_doctype = doc.doctype
			reference_name = doc.name
			user = doc.get(self.user_field)
			rule = self.name

			# incase of zero as result after roundoff
			if not points: return

			# if user_field has no value
			if not user: return

			try:
				create_energy_points_log(reference_doctype, reference_name, {
					'points': points,
					'user': user,
					'rule': rule
				})
			except Exception as e:
				frappe.log_error(frappe.get_traceback(), 'apply_energy_point')


def process_energy_points(doc, state):
	if frappe.flags.in_patch or frappe.flags.in_install or not is_energy_point_enabled():
		return

	for d in frappe.cache_manager.get_doctype_map('Energy Point Rule', doc.doctype,
		dict(reference_doctype = doc.doctype, enabled=1)):
		frappe.get_doc('Energy Point Rule', d.name).apply(doc)

def get_energy_point_doctypes():
	return [
		d.reference_doctype for d in frappe.get_all('Energy Point Rule',
			['reference_doctype'], {'enabled': 1})
	]
