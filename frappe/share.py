# Copyright (c) 2015, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

@frappe.whitelist()
def add(doctype, name, user=None, read=1, write=0, share=0):
	"""Share the given document with a user."""
	if not user:
		user = frappe.session.user

	share_name = frappe.db.get_value("DocShare", {"user": user, "share_name": name,
		"share_doctype": doctype})

	if share_name:
		frappe.delete_doc("DocShare", share_name)

	return frappe.get_doc({
		"doctype": "DocShare",
		"user": user,
		"share_doctype": doctype,
		"share_name": name,
		"read": read,
		"write": write,
		"share": share
	}).insert(ignore_permissions=True)

def remove(doctype, name, user):
	share_name = frappe.db.get_value("DocShare", {"user": user, "share_name": name,
		"share_doctype": doctype})

	if share_name:
		frappe.delete_doc("DocShare", share_name)

@frappe.whitelist()
def set_permission(doctype, name, user, permission_to, value=1):
	"""Set share permission."""
	share_name = frappe.db.get_value("DocShare", {"user": user, "share_name": name,
		"share_doctype": doctype})
	value = int(value)
	if not share_name:
		if value:
			share = add(doctype, name, user, **{permission_to: 1})
		else:
			# no share found, nothing to remove
			share = {}
			pass
	else:
		share = frappe.get_doc("DocShare", share_name)
		share.set(permission_to, value)

		if not value:
			# un-set higher-order permissions too
			if permission_to=="read":
				share.read = share.write = share.share = 0
			elif permission_to=="write":
				share.write = share.share = 0

		share.save()

		if not (share.read or share.write or share.share):
			share.delete()
			share = {}

	return share

@frappe.whitelist()
def get_users(doctype, name):
	"""Get list of users with which this document is shared"""
	return frappe.db.sql("select * from tabDocShare where share_doctype=%s and share_name=%s",
		(doctype, name), as_dict=True)
