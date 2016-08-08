# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe

ignore_doctypes = ("DocType", "Print Format", "Role", "Module Def", "Communication",
	"ToDo")

def notify_link_count(doctype, name):
	'''updates link count for given document'''
	link_count = frappe.cache().get_value('_link_count')
	if not link_count:
		link_count = {}

	if not (doctype, name) in link_count:
		link_count[(doctype, name)] = 1
	else:
		link_count[(doctype, name)] += 1

	frappe.cache().set_value('_link_count', link_count)

def update_link_count():
	'''increment link count in the `idx` column for the given document'''
	link_count = frappe.cache().get_value('_link_count')

	if link_count:
		for key, count in link_count.iteritems():
			if key[0] not in ignore_doctypes:
				try:
					frappe.db.sql('update `tab{0}` set idx = idx + {1} where name=%s'.format(key[0], count),
						key[1])
				except Exception, e:
					if e.args[0]!=1146: # table not found, single
						raise e
	# reset the count
	frappe.cache().delete_value('_link_count')
