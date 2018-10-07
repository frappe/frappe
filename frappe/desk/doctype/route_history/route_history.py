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
	frappe.cache().rpush('route_history', routes)

def save_route_history_to_db():
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
	"""Deletes all route records except last 500 records per user"""

	records_to_keep_limit = 500
	users = frappe.db.sql('''
		SELECT `user`
		FROM `tabRoute History`
		GROUP BY `user`
		HAVING count(`name`) > {limit}
	'''.format(limit=records_to_keep_limit))

	for user in users:
		user = user[0]
		last_record_to_keep = frappe.db.get_all('Route History',
			filters={
				'user': user,
			},
			limit=1,
			limit_start=500,
			fields=['modified'],
			order_by='modified desc')

		frappe.db.sql('''
			DELETE
			FROM `tabRoute History`
			WHERE `modified` <= '{modified}' and `user`='{user}'
		'''.format(modified=last_record_to_keep[0].modified, user=user))