# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class EnergyBadge(Document):
	pass

def process_counter_for_badge(doc, state):
	if doc.get_doc_before_save().count < doc.count:
		badges = frappe.get_all('Energy Badge', filters={
			'track_counter_type': doc.type,
		}, fields=['name', 'count'])

		for badge in badges:
			if not badge.count == doc.count: continue
			user = doc.user
			if user == 'admin@example.com':
				user = 'Administrator'
			user  = frappe.get_doc('User', user)
			user.append('user_badges', {
				'badge': badge.name,
			})
			user.save()
			frappe.db.commit()