import json

import frappe
from frappe.permissions import get_valid_perms
from frappe.utils import cint


def execute():
	frappe.reload_doctype("User Permission")
	user_permissions = frappe.get_all("User Permission", fields=["allow", "name", "user"])

	doctype_to_skip_map = {}

	for permission in user_permissions:
		if (permission.allow, permission.user) not in doctype_to_skip_map:
			doctype_to_skip_map[(permission.allow, permission.user)] = get_doctypes_to_skip(
				permission.allow, permission.user
			)

	if not doctype_to_skip_map:
		return
	for key, doctype_to_skip in doctype_to_skip_map.items():
		if not doctype_to_skip:
			continue
		if not frappe.db.has_column("User Permission", "applicable_for") and frappe.db.has_column(
			"User Permission", "skip_for_doctype"
		):
			doctype_to_skip = "\n".join(doctype_to_skip)
			frappe.db.sql(
				"""
				update `tabUser Permission`
				set skip_for_doctype = %s
				where user=%s and allow=%s
			""",
				(doctype_to_skip, key[1], key[0]),
			)


def get_doctypes_to_skip(doctype, user):
	"""Return doctypes to be skipped from user permission check."""
	doctypes_to_skip = []
	valid_perms = get_user_valid_perms(user) or []
	for perm in valid_perms:
		parent_doctype = perm.parent
		try:
			linked_doctypes = get_linked_doctypes(parent_doctype)
			if doctype not in linked_doctypes:
				continue
		except frappe.DoesNotExistError:
			# if doctype not found (may be due to rename) it should not be considered for skip
			continue

		if not cint(perm.apply_user_permissions):
			# add doctype to skip list if any of the perm does not apply user permission
			doctypes_to_skip.append(parent_doctype)

		elif parent_doctype not in doctypes_to_skip:
			user_permission_doctypes = get_user_permission_doctypes(perm)

			# "No doctypes present" indicates that user permission will be applied to each link field
			if not user_permission_doctypes:
				continue

			elif doctype in user_permission_doctypes:
				continue

			else:
				doctypes_to_skip.append(parent_doctype)
	# remove possible duplicates
	return list(set(doctypes_to_skip))


# store user's valid perms to avoid repeated query
user_valid_perm = {}


def get_user_valid_perms(user):
	if not user_valid_perm.get(user):
		user_valid_perm[user] = get_valid_perms(user=user)
	return user_valid_perm.get(user)


def get_user_permission_doctypes(perm):
	try:
		return json.loads(perm.user_permission_doctypes or "[]")
	except ValueError:
		return []


def get_linked_doctypes(doctype):
	from frappe.permissions import get_linked_doctypes

	linked_doctypes = get_linked_doctypes(doctype)
	child_doctypes = [d.options for d in frappe.get_meta(doctype).get_table_fields()]
	for child_dt in child_doctypes:
		linked_doctypes += get_linked_doctypes(child_dt)
	return linked_doctypes
