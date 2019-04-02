# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.social.doctype.energy_point_settings.energy_point_settings import is_energy_point_enabled
from frappe.social.doctype.energy_point_log.energy_point_log import create_energy_points_log

class EnergyPointRule(Document):
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
			try:
				create_energy_points_log(reference_doctype, reference_name, {
					'points': points,
					'user': user,
					'rule': rule
				})
			except Exception as e:
				frappe.log_error('apply_energy_point', e)


def process_energy_points(doc, state):
	if frappe.flags.in_patch or frappe.flags.in_install or not is_energy_point_enabled():
		return
	# TODO: cache properly
	# energy_point_doctypes = frappe.cache().get_value('energy_point_doctypes', get_energy_point_doctypes)
	# if doc.doctype in energy_point_doctypes:
	rules = frappe.get_all('Energy Point Rule', filters={
		'reference_doctype': doc.doctype,
		'enabled': 1
	})
	for d in rules:
		frappe.get_doc('Energy Point Rule', d.name).apply(doc)

def get_energy_point_doctypes():
	return [
		d.reference_doctype for d in frappe.get_all('Energy Point Rule',
			['reference_doctype'], {'enabled': 1})
	]
