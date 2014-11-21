# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

"""Allow adding of stars to documents"""

import frappe, json
from frappe.model.db_schema import add_column

@frappe.whitelist()
def toggle_star(doctype, name, add=False):
	"""Adds / removes the current user in the `__starred_by` property of the given document.
	If column does not exist, will add it in the database.

	The `_starred_by` property is always set from this function and is ignored if set via
	Document API

	:param doctype: DocType of the document to star
	:param name: Name of the document to star
	:param add: `Yes` if star is to be added. If not `Yes` the star will be removed."""
	try:
		starred_by = frappe.db.get_value(doctype, name, "_starred_by")
		if starred_by:
			starred_by = json.loads(starred_by)
		else:
			starred_by = []

		if add=="Yes":
			if frappe.session.user not in starred_by:
				starred_by.append(frappe.session.user)
		else:
			if frappe.session.user in starred_by:
				starred_by.remove(frappe.session.user)

		frappe.db.sql("""update `tab{0}` set `_starred_by`=%s where name=%s""".format(doctype),
			(json.dumps(starred_by), name))
	except Exception, e:
		if e.args[0]==1054:
			add_column(doctype, "_starred_by", "Text")
			toggle_star(doctype, name)
		else:
			raise
