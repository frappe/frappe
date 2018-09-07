# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import cint

class Counter(Document):
	pass


def update_counter(user, counter_type):
	if user == 'admin@example.com':
		user = 'Administrator'
	count = frappe.db.get_all('Counter', filters={
		'user': user,
		'type': counter_type
	}, fields=['name', 'count'], limit=1)

	if count:
		counter = frappe.get_doc('Counter', count[0].name)
		counter.count += 1
		counter.save()

	else:
		frappe.get_doc({
			'doctype': 'Counter',
			'user': user,
			'type': counter_type,
			'count': 1
		}).insert()