# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import json

class RouteHistory(Document):
	pass

@frappe.whitelist()
def save_route_history(routes):
	# print('Dump history---------------------------')
	frappe.cache().rpush('route_history', routes)

def save_route_history_to_db():
	# print('================================= Saving Route History')
	values = []
	while frappe.cache().llen('route_history') > 0:
		routes = frappe.cache().lpop('route_history')
		routes = json.loads(routes)
		for route_obj in routes:
			route_obj['name'] = frappe.generate_hash('Route History', 10)
			route_obj['modified'] = frappe.utils.now()
			values.append("('{user}', '{name}', '{route}', '{creation}', '{modified}')"
				.format(**route_obj))

	if not values: return

	frappe.db.sql('''
		INSERT INTO `tabRoute History` (`user`, `name`, `route`, `creation`, `modified`)
		VALUES {0}
	'''.format(", ".join(values)), debug=1)

	frappe.db.commit()

def flush_old_route_records():
	frappe.db.sql('''
		SELECT `user`, count(`name`) AS count
		FROM `tabRoute History`
		WHERE count > 20
		GROUP BY `name`
	''')