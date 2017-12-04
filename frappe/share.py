# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import cint

@frappe.whitelist()
def add(doctype, name, user=None, read=1, write=0, share=0, everyone=0, flags=None, notify=0):
	"""Share the given document with a user."""
	if not user:
		user = frappe.session.user

	if not (flags or {}).get("ignore_share_permission"):
		check_share_permission(doctype, name)

	share_name = get_share_name(doctype, name, user, everyone)

	if share_name:
		doc = frappe.get_doc("DocShare", share_name)
	else:
		doc = frappe.new_doc("DocShare")
		doc.update({
			"user": user,
			"share_doctype": doctype,
			"share_name": name,
			"everyone": cint(everyone)
		})

	if flags:
		doc.flags.update(flags)

	doc.update({
		# always add read, since you are adding!
		"read": 1,
		"write": cint(write),
		"share": cint(share)
	})

	doc.save(ignore_permissions=True)
	notify_assignment(user, doctype, name, description=None, notify=notify)

	return doc

def remove(doctype, name, user, flags=None):
	share_name = frappe.db.get_value("DocShare", {"user": user, "share_name": name,
		"share_doctype": doctype})

	if share_name:
		frappe.delete_doc("DocShare", share_name, flags=flags)

@frappe.whitelist()
def set_permission(doctype, name, user, permission_to, value=1, everyone=0):
	"""Set share permission."""
	check_share_permission(doctype, name)

	share_name = get_share_name(doctype, name, user, everyone)
	value = int(value)

	if not share_name:
		if value:
			share = add(doctype, name, user, everyone=everyone, **{permission_to: 1})
		else:
			# no share found, nothing to remove
			share = {}
			pass
	else:
		share = frappe.get_doc("DocShare", share_name)
		share.flags.ignore_permissions = True
		share.set(permission_to, value)

		if not value:
			# un-set higher-order permissions too
			if permission_to=="read":
				share.read = share.write = share.share = 0

		share.save()

		if not (share.read or share.write or share.share):
			share.delete()
			share = {}

	return share

@frappe.whitelist()
def get_users(doctype, name):
	"""Get list of users with which this document is shared"""
	return frappe.db.sql("""select
			`name`, `user`, `read`, `write`, `share`, `everyone`
		from
			tabDocShare
		where
			share_doctype=%s and share_name=%s""",
		(doctype, name), as_dict=True)

def get_shared(doctype, user=None, rights=None):
	"""Get list of shared document names for given user and DocType.

	:param doctype: DocType of which shared names are queried.
	:param user: User for which shared names are queried.
	:param rights: List of rights for which the document is shared. List of `read`, `write`, `share`"""

	if not user:
		user = frappe.session.user

	if not rights:
		rights = ["read"]

	condition = " and ".join(["`{0}`=1".format(right) for right in rights])

	return frappe.db.sql_list("""select share_name from tabDocShare
		where (user=%s {everyone}) and share_doctype=%s and {condition}""".format(
			condition=condition, everyone="or everyone=1" if user!="Guest" else ""),
		(user, doctype))

def get_shared_doctypes(user=None):
	"""Return list of doctypes in which documents are shared for the given user."""
	if not user:
		user = frappe.session.user

	return frappe.db.sql_list("select distinct share_doctype from tabDocShare where (user=%s or everyone=1)", user)

def get_share_name(doctype, name, user, everyone):
	if cint(everyone):
		share_name = frappe.db.get_value("DocShare", {"everyone": 1, "share_name": name,
			"share_doctype": doctype})
	else:
		share_name = frappe.db.get_value("DocShare", {"user": user, "share_name": name,
			"share_doctype": doctype})

	return share_name

def check_share_permission(doctype, name):
	"""Check if the user can share with other users"""
	if not frappe.has_permission(doctype, ptype="share", doc=name):
		frappe.throw(_("No permission to {0} {1} {2}".format("share", doctype, name)), frappe.PermissionError)

def notify_assignment(shared_by, doc_type, doc_name, description=None, notify=0):

	if not (shared_by and doc_type and doc_name): return

	from frappe.utils import get_link_to_form
	document = get_link_to_form(doc_type, doc_name, label="%s: %s" % (doc_type, doc_name))

	arg = {
		'contact': shared_by,
		'txt': _("A new document {0} has been shared by with you {1}.").format(document,
				shared_by),
		'notify': notify
	}

	from frappe.desk.page.chat import chat
	chat.post(**arg)
