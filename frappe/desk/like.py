# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

"""Allow adding of likes to documents"""

import frappe, json
from frappe.model.db_schema import add_column
from frappe import _
from frappe.utils import get_link_to_form

@frappe.whitelist()
def toggle_like(doctype, name, add=False):
	"""Adds / removes the current user in the `__liked_by` property of the given document.
	If column does not exist, will add it in the database.

	The `_liked_by` property is always set from this function and is ignored if set via
	Document API

	:param doctype: DocType of the document to like
	:param name: Name of the document to like
	:param add: `Yes` if like is to be added. If not `Yes` the like will be removed."""

	_toggle_like(doctype, name, add)

def _toggle_like(doctype, name, add, user=None):
	"""Same as toggle_like but hides param `user` from API"""

	if not user:
		user = frappe.session.user

	try:
		liked_by, owner = frappe.db.get_value(doctype, name, ["_liked_by", "owner"])

		# CHANGED: Allow someone to like their own documents as it also works as a bookmark
		# if owner==frappe.session.user and add=="Yes":
		# 	frappe.throw(_("You cannot like something that you created"))

		if liked_by:
			liked_by = json.loads(liked_by)
		else:
			liked_by = []

		if add=="Yes":
			if user not in liked_by:
				liked_by.append(user)
				add_comment(doctype, name)

		else:
			if user in liked_by:
				liked_by.remove(user)
				remove_like(doctype, name)

		frappe.db.set_value(doctype, name, "_liked_by", json.dumps(liked_by), update_modified=False)

	except Exception, e:
		if isinstance(e.args, (tuple, list)) and e.args and e.args[0]==1054:
			add_column(doctype, "_liked_by", "Text")
			_toggle_like(doctype, name, add, user)
		else:
			raise

def remove_like(doctype, name):
	"""Remove previous Like"""
	# remove Comment
	frappe.delete_doc("Comment", [c.name for c in frappe.get_all("Comment",
		filters={
			"comment_doctype": doctype,
			"comment_docname": name,
			"comment_by": frappe.session.user,
			"comment_type": "Like"
		}
	)], ignore_permissions=True)

	# remove Feed
	frappe.delete_doc("Feed", [c.name for c in frappe.get_all("Feed",
		filters={
			"doc_type": doctype,
			"doc_name": name,
			"owner": frappe.session.user,
			"feed_type": "Like"
		}
	)], ignore_permissions=True)

def add_comment(doctype, name):
	doc = frappe.get_doc(doctype, name)

	if doctype=="Comment":
		link = get_link_to_form(doc.comment_doctype, doc.comment_docname,
			"{0} {1}".format(_(doc.comment_doctype), doc.comment_docname))
		doc.add_comment("Like", _("Comment: {0} in {1}").format("<b>" + doc.comment + "</b>", link),
			reference_doctype=doc.comment_doctype, reference_name=doc.comment_docname)

	elif doctype=="Communication":
		link = get_link_to_form(doc.reference_doctype, doc.reference_name,
			"{0} {1}".format(_(doc.reference_doctype), doc.reference_name))

		doc.add_comment("Like", _("Communication: {0} in {1}").format("<b>" + doc.subject + "</b>", link),
			reference_doctype=doc.reference_doctype, reference_name=doc.reference_name)

	else:
		doc.add_comment("Like", _("Liked"))
