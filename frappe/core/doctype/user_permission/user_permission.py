# Copyright (c) 2021, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
from typing import Any

import frappe
from frappe import _
from frappe.core.utils import find
from frappe.desk.form.linked_with import get_linked_doctypes
from frappe.model.document import Document
from frappe.utils import cstr


class UserPermission(Document):
	_DOCTYPE_NAME = "User Permission"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		allow: DF.Link
		applicable_for: DF.Link | None
		apply_to_all_doctypes: DF.Check
		for_value: DF.DynamicLink
		hide_descendants: DF.Check
		is_default: DF.Check
		user: DF.Link
	# end: auto-generated types

	def validate(self):
		self.validate_user_permission()
		self.validate_default_permission()

	def on_update(self):
		frappe.cache.hdel("user_permissions", self.user)
		frappe.publish_realtime("update_user_permissions", user=self.user, after_commit=True)

	def on_trash(self):
		frappe.cache.hdel("user_permissions", self.user)
		frappe.publish_realtime("update_user_permissions", user=self.user, after_commit=True)

	def validate_user_permission(self):
		"""checks for duplicate user permission records"""

		duplicate_exists = frappe.get_all(
			self.doctype,
			filters={
				"allow": self.allow,
				"for_value": self.for_value,
				"user": self.user,
				"applicable_for": cstr(self.applicable_for),
				"apply_to_all_doctypes": self.apply_to_all_doctypes,
				"name": ["!=", self.name],
			},
			limit=1,
		)
		if duplicate_exists:
			frappe.throw(_("User permission already exists"), frappe.DuplicateEntryError)

	def validate_default_permission(self):
		"""validate user permission overlap for default value of a particular doctype"""
		overlap_exists = []
		if self.is_default:
			overlap_exists = frappe.get_all(
				self.doctype,
				filters={"allow": self.allow, "user": self.user, "is_default": 1, "name": ["!=", self.name]},
				or_filters={
					"applicable_for": cstr(self.applicable_for),
					"apply_to_all_doctypes": 1,
				},
				limit=1,
			)
		if overlap_exists:
			ref_link = frappe.get_desk_link(self.doctype, overlap_exists[0].name)
			frappe.throw(_("{0} has already assigned default value for {1}.").format(ref_link, self.allow))

	def get_permission_log_options(self, event=None):
		pass


def send_user_permissions(bootinfo):
	from frappe.core.api.permissions import get_user_permissions

	bootinfo.user["user_permissions"] = get_user_permissions()


def user_permission_exists(user, allow, for_value, applicable_for=None):
	"""Checks if similar user permission already exists"""
	from frappe.core.api.permissions import get_user_permissions

	user_permissions = get_user_permissions(user).get(allow, [])
	if not user_permissions:
		return None
	return find(
		user_permissions,
		lambda perm: perm["doc"] == for_value and perm.get("applicable_for") == applicable_for,
	)


def get_permitted_documents(doctype):
	"""Return permitted documents from the given doctype for the session user."""
	from frappe.core.api.permissions import get_user_permissions

	# sort permissions in a way to make the first permission in the list to be default
	user_perm_list = sorted(
		get_user_permissions().get(doctype, []), key=lambda x: x.get("is_default"), reverse=True
	)

	return [d.get("doc") for d in user_perm_list if d.get("doc")]


def insert_user_perm(
	user, doctype, docname, is_default=0, hide_descendants=0, apply_to_all=None, applicable=None
):
	user_perm = frappe.new_doc("User Permission")
	user_perm.user = user
	user_perm.allow = doctype
	user_perm.for_value = docname
	user_perm.is_default = is_default
	user_perm.hide_descendants = hide_descendants
	if applicable:
		user_perm.applicable_for = applicable
		user_perm.apply_to_all_doctypes = 0
	else:
		user_perm.apply_to_all_doctypes = 1
	user_perm.insert()


def remove_applicable(perm_applied_docs, user, doctype, docname):
	for applicable_for in perm_applied_docs:
		frappe.db.delete(
			"User Permission",
			{
				"applicable_for": applicable_for,
				"for_value": docname,
				"allow": doctype,
				"user": user,
			},
		)


def remove_apply_to_all(user, doctype, docname):
	frappe.db.delete(
		"User Permission",
		{
			"apply_to_all_doctypes": 1,
			"for_value": docname,
			"allow": doctype,
			"user": user,
		},
	)


def update_applicable(already_applied, to_apply, user, doctype, docname):
	for applied in already_applied:
		if applied not in to_apply:
			frappe.db.delete(
				"User Permission",
				{
					"applicable_for": applied,
					"for_value": docname,
					"allow": doctype,
					"user": user,
				},
			)


# `get_user_permissions`, `get_applicable_for_doctype_list`, `check_applicable_doc_perm`, `clear_user_permissions`, `add_user_permissions` moved to frappe.core.api.permissions.
# The aliases keep the old dotted paths working; resolved lazily to avoid
# circular imports.
_MOVED_TO_PERMISSIONS_API = {
	"get_user_permissions": "get_user_permissions",
	"get_applicable_for_doctype_list": "get_applicable_for_doctype_list",
	"check_applicable_doc_perm": "check_applicable_doc_perm",
	"clear_user_permissions": "clear_user_permissions",
	"add_user_permissions": "add_user_permissions",
}


def __getattr__(name: str):
	if new_name := _MOVED_TO_PERMISSIONS_API.get(name):
		from frappe.core.api import permissions

		return getattr(permissions, new_name)
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
