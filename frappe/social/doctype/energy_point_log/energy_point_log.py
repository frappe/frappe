# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import cint

class EnergyPointLog(Document):
	def after_insert(self):
		update_user_energy_points(self.points, self.user)

def create_energy_point_log(ref_doctype, ref_name, doc):
	doc = frappe._dict(doc)
	log_exists = frappe.db.exists('Energy Point Log', {
		'user': doc.user,
		'rule': doc.rule,
		'reference_doctype': ref_doctype,
		'reference_name': ref_name
	})
	if log_exists:
		return

	_doc = frappe.new_doc('Energy Point Log')
	_doc.reference_doctype = ref_doctype
	_doc.reference_name = ref_name
	_doc.update(doc)
	_doc.insert(ignore_permissions=True)
	return _doc

def update_user_energy_points(points, user):
	points = cint(points)

	previous_points = frappe.db.get_value('User', user, 'energy_points')
	new_points = cint(previous_points) + points
	frappe.db.set_value('User', user, 'energy_points', new_points)
	message='=== You gained <b>{}</b> points ==='.format(points)
	frappe.publish_realtime('points_gained', message=message , user=user)