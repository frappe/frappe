# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import cint

ENERGY_POINT_VALUES = {
	'issue_closed': 2,
	'instant_reply_on_issue': 2,
	'feedback_point_multiplier': 2,
	'github_pull_request_merge': 2,
	'github_pull_request_review_submit': 2,
	'github_issue_open': 1,
	'github_issue_close': 2,
}

class EnergyPointLog(Document):
	def after_insert(self):
		update_user_energy_points(self.points, self.user)

def process_for_energy_points(doc, state):
	if frappe.flags.in_patch: return
	doc_action = doc.get('_action')
	if not doc_action: return

	point_rules = frappe.get_all('Energy Point Rule', filters={
		'reference_doctype': doc.get('doctype'),
	}, fields=['name', 'points', 'rule_name', '`condition`', 'user_field'], debug=1)
	print(point_rules)
	for point_rule in point_rules:
		print(point_rule.condition)
		if frappe.safe_eval(point_rule.condition, None, {'doc': doc}):
			create_energy_point_log(
				points=point_rule.points,
				reason=None,
				reference_doctype=doc.doctype,
				reference_name=doc.name,
				user=doc.get(point_rule.user_field),
				rule=point_rule.name
			)

def create_energy_point_log(points, reason, reference_doctype, reference_name, user=None, rule=None):
	print('===================in=========', user, points)
	if not user:
		user = frappe.session.user

	if user == 'admin@example.com':
		user = 'Administrator'
	frappe.get_doc({
		'doctype': 'Energy Point Log',
		'points': points,
		'user': user,
		'rule': rule,
		'reason': reason,
		'reference_doctype': reference_doctype,
		'reference_name': reference_name
	}).insert(ignore_permissions=True)

def update_user_energy_points(point, user=None):
	point = cint(point)
	if not point: return
	# TODO: find alternative
	if user == 'admin@erpnext.com': user = 'Administrator'
	if not user: user = frappe.session.user
	previous_point = frappe.db.get_value('User', user, 'energy_points')
	new_point = cint(previous_point) + point
	frappe.db.set_value('User', user, 'energy_points', new_point)

	print('================= {} gained {} points ==================='.format(user, point))