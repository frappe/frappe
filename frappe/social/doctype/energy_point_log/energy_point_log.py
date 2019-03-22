# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import cint

class EnergyPointLog(Document):
	def after_insert(self):
		if self.type != 'Review':
			message='=== You gained <b>{}</b> points ==='.format(self.points)
			frappe.publish_realtime('points_gained', message=message , user=self.user)

def create_energy_points_log(ref_doctype, ref_name, doc):
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

def create_review_points_log(user, points, reason=None):
	return frappe.get_doc({
		'doctype': 'Energy Point Log',
		'points': points,
		'type': 'Review',
		'user': user,
		'reason': reason
	}).insert(ignore_permissions=True)

def get_energy_points(user, points_type=None):
	if not points_type:
		points_type = ['NOT IN', ('Review')]

	log = frappe.db.get_all('Energy Point Log', filters={
		'user': user,
		'type': points_type
	}, fields=['SUM(`points`) as points'], group_by='user')

	return log[0].points if log else 0