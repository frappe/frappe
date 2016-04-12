# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
"""
Model utilities, unclassified functions
"""

def set_default(doc, key):
	"""Set is_default property of given doc and unset all others filtered by given key."""
	if not doc.is_default:
		frappe.db.set(doc, "is_default", 1)

	frappe.db.sql("""update `tab%s` set `is_default`=0
		where `%s`=%s and name!=%s""" % (doc.doctype, key, "%s", "%s"),
		(doc.get(key), doc.name))

def set_field_property(filters, key, value):
	'''utility set a property in all fields of a particular type'''
	docs = [frappe.get_doc('DocType', d.parent) for d in \
		frappe.get_all("DocField", fields=['parent'], filters=filters)]

	for d in docs:
		d.get('fields', filters)[0].set(key, value)
		d.save()
		print 'Updated {0}'.format(d.name)

	frappe.db.commit()
