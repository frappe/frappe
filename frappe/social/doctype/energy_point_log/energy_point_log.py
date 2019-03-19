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

	point_rule = frappe.get_all('Energy Point Rule', filters={
		'reference_doctype': doc.get('doctype'),
	}, fields=['points', 'rule_name'], limit=1)

	if point_rule:
		point_rule = point_rule[0]
		print(point_rule)
		if frappe.safe_eval(point_rule.condition or True, None, {'doc': doc}):
			create_energy_point_log(
				point_rule.points,
				"Action {0} on {1}".format(point_rule.rule_name, doc.name),
				doc.doctype,
				doc.name,
				doc.get(point_rule.user_field)
			)

def get_event_type(state):
	return state.capitalize()

def create_energy_point_log(points, reason, reference_doctype, reference_name, user=None):
	print('===================in=========', user, points)
	if not user:
		user = frappe.session.user

	if user == 'admin@example.com':
		user = 'Administrator'
	frappe.get_doc({
		'doctype': 'Energy Point Log',
		'points': points,
		'user': user,
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
	previous_point = frappe.db.get_value('User', user, 'energy_point')
	new_point = cint(previous_point) + point
	frappe.db.set_value('User', user, 'energy_point', new_point)

	print('================= {} gained {} points ==================='.format(user, point))