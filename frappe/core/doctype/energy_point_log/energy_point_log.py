# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class EnergyPointLog(Document):
	pass

def update_log(doc, state):

	if doc.is_new() and doc._action =="save":
		event_type = "Create"
	else:
		event_type = get_event_type(doc._action)

	point_rule = frappe.get_all('Energy Point Rule', filters={
		'reference_doctype': doc.get('doctype'),
		'event_type': event_type
	}, fields=['point', 'rule_name'], limit=1)

	if point_rule:
		point_rule = point_rule[0]
		if(point_rule.condition and frappe.safe_eval(point_rule.condition, None, {'doc': doc})):
			update_user_energy_point(point_rule.point)
			add_energy_point_log(doc, point_rule)

def update_user_energy_point(point_value, user=None):
	if not user: user = frappe.session.user
	previous_point = frappe.db.get_value('User', user, 'energy_point')
	new_point = previous_point + point_value
	frappe.db.set_value('User', user, 'energy_point', new_point)

def get_event_type(state):
	return state.capitalize()

def add_energy_point_log(doc, point_rule, user=None):
	if not user: user = frappe.session.user
	log = frappe.get_doc({
		'doctype': 'Energy Point Log',
		'user': user,
		'reason': "Action {0} on {1}".format(point_rule.rule_name, doc.name),
		'point': point_rule.point
	})
	log.insert(ignore_permissions=True)
