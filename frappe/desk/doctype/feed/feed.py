# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: See license.txt

from __future__ import unicode_literals
import frappe
import frappe.defaults
import frappe.permissions
from frappe.model.document import Document
from frappe.utils import get_fullname
from frappe import _

exclude_from_linked_with = True

class Feed(Document):
	pass

def on_doctype_update():
	if not frappe.db.sql("""show index from `tabFeed`
		where Key_name="feed_doctype_docname_index" """):
		frappe.db.commit()
		frappe.db.sql("""alter table `tabFeed`
			add index feed_doctype_docname_index(doc_type, doc_name)""")

def get_permission_query_conditions(user):
	if not user: user = frappe.session.user

	if not frappe.permissions.apply_user_permissions("Feed", "read", user):
		return ""

	user_permissions = frappe.defaults.get_user_permissions(user)
	can_read = frappe.get_user().get_can_read()

	can_read_doctypes = ['"{}"'.format(doctype) for doctype in
		list(set(can_read) - set(user_permissions.keys()))]

	if not can_read_doctypes:
		return ""

	conditions = ["tabFeed.doc_type in ({})".format(", ".join(can_read_doctypes))]

	if user_permissions:
		can_read_docs = []
		for doctype, names in user_permissions.items():
			for n in names:
				can_read_docs.append('"{}|{}"'.format(doctype, n))

		if can_read_docs:
			conditions.append("concat_ws('|', tabFeed.doc_type, tabFeed.doc_name) in ({})".format(
				", ".join(can_read_docs)))

	return "(" + " or ".join(conditions) + ")"

def has_permission(doc, user):
	return frappe.has_permission(doc.doc_type, "read", doc.doc_name, user=user)

def update_feed(doc, method=None):
	"adds a new feed"
	if frappe.flags.in_patch or frappe.flags.in_install or frappe.flags.in_import:
		return

	if doc.doctype == "Feed" or doc.meta.issingle:
		return

	if hasattr(doc, "get_feed"):
		feed = doc.get_feed()

		if feed:
			if isinstance(feed, basestring):
				feed = {"subject": feed}

			feed = frappe._dict(feed)
			doctype = feed.doctype or doc.doctype
			name = feed.name or doc.name

			# delete earlier feed
			frappe.db.sql("""delete from tabFeed
				where doc_type=%s and doc_name=%s
				and ifnull(feed_type,'')=''""", (doctype, name))

			frappe.get_doc({
				"doctype": "Feed",
				"feed_type": feed.feed_type or "",
				"doc_type": doctype,
				"doc_name": name,
				"subject": feed.subject,
				"full_name": get_fullname(doc.owner)
			}).insert(ignore_permissions=True)

def login_feed(login_manager):
	frappe.get_doc({
		"doctype": "Feed",
		"feed_type": "Login",
		"subject": _("{0} logged in").format(get_fullname(login_manager.user)),
		"full_name": get_fullname(login_manager.user)
	}).insert(ignore_permissions=True)
