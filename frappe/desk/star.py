# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
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

	_toggle_star(doctype, name, add)

def _toggle_star(doctype, name, add=False, user=None):
	"""Same as toggle_star but hides param `user` from API"""

	if not user:
		user = frappe.session.user

	try:
		starred_by = frappe.db.get_value(doctype, name, "_starred_by")
		if starred_by:
			starred_by = json.loads(starred_by)
		else:
			starred_by = []

		if add=="Yes":
			if user not in starred_by:
				starred_by.append(user)
		else:
			if user in starred_by:
				starred_by.remove(user)

		frappe.db.sql("""update `tab{0}` set `_starred_by`=%s where name=%s""".format(doctype),
			(json.dumps(starred_by), name))

	except Exception, e:
		if e.args[0]==1054:
			add_column(doctype, "_starred_by", "Text")
			_toggle_star(doctype, name, add, user)
		else:
			raise
