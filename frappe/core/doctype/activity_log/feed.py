# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: See license.txt

from __future__ import unicode_literals

from six import string_types

import frappe
import frappe.permissions
from frappe import _
from frappe.core.doctype.activity_log.activity_log import add_authentication_log
from frappe.utils import get_fullname


def update_feed(doc, method=None):
	if frappe.flags.in_patch or frappe.flags.in_install or frappe.flags.in_import:
		return

	if doc._action != "save" or doc.flags.ignore_feed:
		return

	if doc.doctype == "Activity Log" or doc.meta.issingle:
		return

	if hasattr(doc, "get_feed"):
		feed = doc.get_feed()

		if feed:
			if isinstance(feed, string_types):
				feed = {"subject": feed}

			feed = frappe._dict(feed)
			doctype = feed.doctype or doc.doctype
			name = feed.name or doc.name

			# delete earlier feed
			frappe.db.sql(
				"""delete from `tabActivity Log`
				where
					reference_doctype=%s and reference_name=%s
					and link_doctype=%s""",
				(doctype, name, feed.link_doctype),
			)
			frappe.get_doc(
				{
					"doctype": "Activity Log",
					"reference_doctype": doctype,
					"reference_name": name,
					"subject": feed.subject,
					"full_name": get_fullname(doc.owner),
					"reference_owner": frappe.db.get_value(doctype, name, "owner"),
					"link_doctype": feed.link_doctype,
					"link_name": feed.link_name,
				}
			).insert(ignore_permissions=True)


def login_feed(login_manager):
	if login_manager.user != "Guest":
		subject = _("{0} logged in").format(get_fullname(login_manager.user))
		add_authentication_log(subject, login_manager.user)


def logout_feed(user, reason):
	if user and user != "Guest":
		subject = _("{0} logged out: {1}").format(get_fullname(user), frappe.bold(reason))
		add_authentication_log(subject, user, operation="Logout")


def get_feed_match_conditions(user=None, doctype="Comment"):
	if not user:
		user = frappe.session.user

	conditions = [
		"`tab{doctype}`.owner={user} or `tab{doctype}`.reference_owner={user}".format(
			user=frappe.db.escape(user), doctype=doctype
		)
	]

	user_permissions = frappe.permissions.get_user_permissions(user)
	can_read = frappe.get_user().get_can_read()

	can_read_doctypes = [
		"'{}'".format(dt) for dt in list(set(can_read) - set(list(user_permissions)))
	]

	if can_read_doctypes:
		conditions += [
			"""(`tab{doctype}`.reference_doctype is null
			or `tab{doctype}`.reference_doctype = ''
			or `tab{doctype}`.reference_doctype
			in ({values}))""".format(
				doctype=doctype, values=", ".join(can_read_doctypes)
			)
		]

		if user_permissions:
			can_read_docs = []
			for dt, obj in user_permissions.items():
				for n in obj:
					can_read_docs.append("{}|{}".format(frappe.db.escape(dt), frappe.db.escape(n.get("doc", ""))))

			if can_read_docs:
				conditions.append(
					"concat_ws('|', `tab{doctype}`.reference_doctype, `tab{doctype}`.reference_name) in ({values})".format(
						doctype=doctype, values=", ".join(can_read_docs)
					)
				)

	return "(" + " or ".join(conditions) + ")"
