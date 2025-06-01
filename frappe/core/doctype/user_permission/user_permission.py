# Copyright (c) 2021, nts Technologies and contributors
# License: MIT. See LICENSE

import json

import nts
from nts import _
from nts.core.utils import find
from nts.desk.form.linked_with import get_linked_doctypes
from nts.model.document import Document
from nts.utils import cstr


class UserPermission(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from nts.types import DF

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
		nts.cache.hdel("user_permissions", self.user)
		nts.publish_realtime("update_user_permissions", user=self.user, after_commit=True)

	def on_trash(self):
		nts.cache.hdel("user_permissions", self.user)
		nts.publish_realtime("update_user_permissions", user=self.user, after_commit=True)

	def validate_user_permission(self):
		"""checks for duplicate user permission records"""

		duplicate_exists = nts.get_all(
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
			nts.throw(_("User permission already exists"), nts.DuplicateEntryError)

	def validate_default_permission(self):
		"""validate user permission overlap for default value of a particular doctype"""
		overlap_exists = []
		if self.is_default:
			overlap_exists = nts.get_all(
				self.doctype,
				filters={"allow": self.allow, "user": self.user, "is_default": 1, "name": ["!=", self.name]},
				or_filters={
					"applicable_for": cstr(self.applicable_for),
					"apply_to_all_doctypes": 1,
				},
				limit=1,
			)
		if overlap_exists:
			ref_link = nts.get_desk_link(self.doctype, overlap_exists[0].name)
			nts.throw(_("{0} has already assigned default value for {1}.").format(ref_link, self.allow))


def send_user_permissions(bootinfo):
	bootinfo.user["user_permissions"] = get_user_permissions()


@nts.whitelist()
def get_user_permissions(user=None):
	"""Get all users permissions for the user as a dict of doctype"""
	# if this is called from client-side,
	# user can access only his/her user permissions
	if nts.request and nts.local.form_dict.cmd == "get_user_permissions":
		user = nts.session.user

	if not user:
		user = nts.session.user

	if not user or user in ("Administrator", "Guest"):
		return {}

	cached_user_permissions = nts.cache.hget("user_permissions", user)

	if cached_user_permissions is not None:
		return cached_user_permissions

	out = {}

	def add_doc_to_perm(perm, doc_name, is_default):
		# group rules for each type
		# for example if allow is "Customer", then build all allowed customers
		# in a list
		if not out.get(perm.allow):
			out[perm.allow] = []

		out[perm.allow].append(
			nts._dict(
				{"doc": doc_name, "applicable_for": perm.get("applicable_for"), "is_default": is_default}
			)
		)

	try:
		for perm in nts.get_all(
			"User Permission",
			fields=["allow", "for_value", "applicable_for", "is_default", "hide_descendants"],
			filters=dict(user=user),
		):
			meta = nts.get_meta(perm.allow)
			add_doc_to_perm(perm, perm.for_value, perm.is_default)

			if meta.is_nested_set() and not perm.hide_descendants:
				decendants = nts.db.get_descendants(perm.allow, perm.for_value)
				for doc in decendants:
					add_doc_to_perm(perm, doc, False)

		out = nts._dict(out)
		nts.cache.hset("user_permissions", user, out)
	except nts.db.SQLError as e:
		if nts.db.is_table_missing(e):
			# called from patch
			pass

	return out


def user_permission_exists(user, allow, for_value, applicable_for=None):
	"""Checks if similar user permission already exists"""
	user_permissions = get_user_permissions(user).get(allow, [])
	if not user_permissions:
		return None
	return find(
		user_permissions,
		lambda perm: perm["doc"] == for_value and perm.get("applicable_for") == applicable_for,
	)


@nts.whitelist()
@nts.validate_and_sanitize_search_inputs
def get_applicable_for_doctype_list(doctype, txt, searchfield, start, page_len, filters):
	linked_doctypes_map = get_linked_doctypes(doctype, True)

	linked_doctypes = []
	for linked_doctype, linked_doctype_values in linked_doctypes_map.items():
		linked_doctypes.append(linked_doctype)
		child_doctype = linked_doctype_values.get("child_doctype")
		if child_doctype:
			linked_doctypes.append(child_doctype)

	linked_doctypes += [doctype]

	if txt:
		linked_doctypes = [d for d in linked_doctypes if txt.lower() in d.lower()]

	linked_doctypes.sort()

	return [[doctype] for doctype in linked_doctypes[start:page_len]]


def get_permitted_documents(doctype):
	"""Returns permitted documents from the given doctype for the session user"""
	# sort permissions in a way to make the first permission in the list to be default
	user_perm_list = sorted(
		get_user_permissions().get(doctype, []), key=lambda x: x.get("is_default"), reverse=True
	)

	return [d.get("doc") for d in user_perm_list if d.get("doc")]


@nts.whitelist()
def check_applicable_doc_perm(user, doctype, docname):
	nts.only_for("System Manager")
	applicable = []
	doc_exists = nts.get_all(
		"User Permission",
		fields=["name"],
		filters={
			"user": user,
			"allow": doctype,
			"for_value": docname,
			"apply_to_all_doctypes": 1,
		},
		limit=1,
	)
	if doc_exists:
		applicable = get_linked_doctypes(doctype).keys()
	else:
		data = nts.get_all(
			"User Permission",
			fields=["applicable_for"],
			filters={
				"user": user,
				"allow": doctype,
				"for_value": docname,
			},
		)
		for permission in data:
			applicable.append(permission.applicable_for)
	return applicable


@nts.whitelist()
def clear_user_permissions(user, for_doctype):
	nts.only_for("System Manager")
	total = nts.db.count("User Permission", {"user": user, "allow": for_doctype})

	if total:
		nts.db.delete(
			"User Permission",
			{
				"allow": for_doctype,
				"user": user,
			},
		)
		nts.clear_cache()

	return total


@nts.whitelist()
def add_user_permissions(data):
	"""Add and update the user permissions"""
	nts.only_for("System Manager")
	if isinstance(data, str):
		data = json.loads(data)
	data = nts._dict(data)

	# get all doctypes on whom this permission is applied
	perm_applied_docs = check_applicable_doc_perm(data.user, data.doctype, data.docname)
	exists = nts.db.exists(
		"User Permission",
		{
			"user": data.user,
			"allow": data.doctype,
			"for_value": data.docname,
			"apply_to_all_doctypes": 1,
		},
	)
	if data.apply_to_all_doctypes == 1 and not exists:
		remove_applicable(perm_applied_docs, data.user, data.doctype, data.docname)
		insert_user_perm(
			data.user, data.doctype, data.docname, data.is_default, data.hide_descendants, apply_to_all=1
		)
		return 1
	elif len(data.applicable_doctypes) > 0 and data.apply_to_all_doctypes != 1:
		remove_apply_to_all(data.user, data.doctype, data.docname)
		update_applicable(perm_applied_docs, data.applicable_doctypes, data.user, data.doctype, data.docname)
		for applicable in data.applicable_doctypes:
			if applicable not in perm_applied_docs:
				insert_user_perm(
					data.user,
					data.doctype,
					data.docname,
					data.is_default,
					data.hide_descendants,
					applicable=applicable,
				)
			elif exists:
				insert_user_perm(
					data.user,
					data.doctype,
					data.docname,
					data.is_default,
					data.hide_descendants,
					applicable=applicable,
				)
		return 1
	return 0


def insert_user_perm(
	user, doctype, docname, is_default=0, hide_descendants=0, apply_to_all=None, applicable=None
):
	user_perm = nts.new_doc("User Permission")
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
		nts.db.delete(
			"User Permission",
			{
				"applicable_for": applicable_for,
				"for_value": docname,
				"allow": doctype,
				"user": user,
			},
		)


def remove_apply_to_all(user, doctype, docname):
	nts.db.delete(
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
			nts.db.delete(
				"User Permission",
				{
					"applicable_for": applied,
					"for_value": docname,
					"allow": doctype,
					"user": user,
				},
			)
