# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
import json
from frappe.model.document import Document
from frappe.utils import cint

class EnergyPointLog(Document):
	def after_insert(self):
		if self.type == 'Auto':
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

@frappe.whitelist()
def review(doc, points, to_user, reason, review_type='Appreciation'):
	current_review_points = get_energy_points(frappe.session.user, 'Review')
	doc = frappe._dict(json.loads(doc))
	points = cint(points)
	if current_review_points < abs(points):
		frappe.msgprint(_('You do not have enough review points'))
		return

	# deduct review points from reviewer
	create_review_points_log(
		user=frappe.session.user,
		points=-abs(points),
		reason=reason
	)

	create_energy_points_log(doc.doctype, doc.name, {
		'type': review_type,
		'reason': reason,
		'points': points,
		'user': to_user
	})

	message = _('{} appreciated your work on {} with {} points'.format(
		frappe.session.user,
		doc.name,
		points
	))

	frappe.publish_realtime('points_gained', message=message , user=to_user)