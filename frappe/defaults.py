# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.cache_manager import clear_defaults_cache, common_default_keys
from frappe.query_builder import DocType
from frappe.utils.data import cstr

# Note: DefaultValue records are identified by parent (e.g. __default, __global)


def set_user_default(key, value, user=None, parenttype=None):
	set_default(key, value, user or frappe.session.user, parenttype)


def add_user_default(key, value, user=None, parenttype=None):
	add_default(key, value, user or frappe.session.user, parenttype)


def get_user_default(key, user=None):
	user_defaults = get_defaults(user or frappe.session.user)
	d = user_defaults.get(key, None)

	if is_a_user_permission_key(key):
		if d and isinstance(d, list | tuple) and len(d) == 1:
			# Use User Permission value when only when it has a single value
			d = d[0]
		else:
			d = user_defaults.get(frappe.scrub(key), None)
			user_permission_default = get_user_permission_default(key, user_defaults)
			if not d:
				# If no default value is found, use the User Permission value
				d = user_permission_default

	value = (isinstance(d, list | tuple) and d[0]) or d
	if not_in_user_permission(key, value, user):
		return

	return value


def get_user_permission_default(key, defaults):
	permissions = get_user_permissions()
	user_default = ""
	if permissions.get(key):
		# global default in user permission
		for item in permissions.get(key):
			doc = item.get("doc")
			if defaults.get(key) == doc:
				user_default = doc

		for item in permissions.get(key):
			if item.get("is_default"):
				user_default = item.get("doc")
				break

	return user_default


def get_user_default_as_list(key, user=None):
	user_defaults = get_defaults(user or frappe.session.user)
	d = user_defaults.get(key, None)

	if is_a_user_permission_key(key):
		if d and isinstance(d, list | tuple) and len(d) == 1:
			# Use User Permission value when only when it has a single value
			d = [d[0]]

		else:
			d = user_defaults.get(frappe.scrub(key), None)

	d = list(filter(None, ((not isinstance(d, list | tuple)) and [d]) or d))

	# filter default values if not found in user permission
	return [value for value in d if not not_in_user_permission(key, value)]


def is_a_user_permission_key(key):
	return ":" not in key and key != frappe.scrub(key)


def not_in_user_permission(key, value, user=None):
	# return true or false based on if value exist in user permission
	user = user or frappe.session.user
	user_permission = get_user_permissions(user).get(frappe.unscrub(key)) or []

	for perm in user_permission:
		# doc found in user permission
		if perm.get("doc") == value:
			return False

	# return true only if user_permission exists
	return True if user_permission else False


def get_user_permissions(user=None):
	from frappe.core.doctype.user_permission.user_permission import (
		get_user_permissions as _get_user_permissions,
	)

	"""Return frappe.core.doctype.user_permissions.user_permissions._get_user_permissions (kept for backward compatibility)"""
	return _get_user_permissions(user)


def get_defaults(user=None):
	global_defaults = get_defaults_for()

	if not user:
		user = frappe.session.user if frappe.session else "Guest"

	if not user:
		return global_defaults

	defaults = global_defaults.copy()
	defaults.update(get_defaults_for(user))
	defaults.update(user=user, owner=user)

	return defaults


def clear_user_default(key, user=None):
	clear_default(key, parent=user or frappe.session.user)


# Global


def set_global_default(key, value):
	set_default(key, value, "__default")


def add_global_default(key, value):
	add_default(key, value, "__default")


def get_global_default(key):
	d = get_defaults().get(key, None)

	value = (isinstance(d, list | tuple) and d[0]) or d
	if not_in_user_permission(key, value):
		return

	return value


# Common


def set_default(key, value, parent, parenttype="__default"):
	"""Override or add a default value.
	Adds default value in table `tabDefaultValue`.

	:param key: Default key.
	:param value: Default value.
	:param parent: Usually, **User** to whom the default belongs.
	:param parenttype: [optional] default is `__default`."""
	table = DocType("DefaultValue")
	current_value = (
		frappe.qb.from_(table)
		.where((table.defkey == key) & (table.parent == parent))
		.select(table.defvalue)
		.for_update()
		.run(as_dict=True)
	)
	if current_value:
		if current_value[0].defvalue == cstr(value):
			# Nothing has changed
			return
		frappe.db.delete("DefaultValue", {"defkey": key, "parent": parent})
	if value is not None:
		add_default(key, value, parent)
	else:
		_clear_cache(parent)

	if parent:
		clear_defaults_cache(parent)


def add_default(key, value, parent, parenttype=None):
	d = frappe.get_doc(
		{
			"doctype": "DefaultValue",
			"parent": parent,
			"parenttype": parenttype or "__default",
			"parentfield": "system_defaults",
			"defkey": key,
			"defvalue": value,
		}
	)
	d.insert(ignore_permissions=True)
	_clear_cache(parent)


def clear_default(key=None, value=None, parent=None, name=None, parenttype=None):
	"""Clear a default value by any of the given parameters and delete caches.

	:param key: Default key.
	:param value: Default value.
	:param parent: User name, or `__global`, `__default`.
	:param name: Default ID.
	:param parenttype: Clear defaults table for a particular type e.g. **User**.
	"""
	filters = {}

	if name:
		filters.update({"name": name})

	else:
		if key:
			filters.update({"defkey": key})

		if value:
			filters.update({"defvalue": value})

		if parent:
			filters.update({"parent": parent})

		if parenttype:
			filters.update({"parenttype": parenttype})

	if parent:
		clear_defaults_cache(parent)
	else:
		clear_defaults_cache("__default")
		clear_defaults_cache("__global")

	if not filters:
		raise Exception("[clear_default] No key specified.")

	frappe.db.delete("DefaultValue", filters)

	_clear_cache(parent)


def get_defaults_for(parent="__default"):
	"""get all defaults"""

	key = f"defaults::{parent}"
	defaults = frappe.client_cache.get_value(key)

	if defaults is None:
		# sort descending because first default must get precedence
		table = DocType("DefaultValue")
		res = (
			frappe.qb.from_(table)
			.where(table.parent == parent)
			.select(table.defkey, table.defvalue)
			.orderby("creation")
			.run(as_dict=True)
		)

		defaults = frappe._dict()
		for d in res:
			if d.defkey in defaults:
				# listify
				if not isinstance(defaults[d.defkey], list) and defaults[d.defkey] != d.defvalue:
					defaults[d.defkey] = [defaults[d.defkey]]

				if d.defvalue not in defaults[d.defkey]:
					defaults[d.defkey].append(d.defvalue)

			elif d.defvalue is not None:
				defaults[d.defkey] = d.defvalue

		frappe.client_cache.set_value(key, defaults)

	return defaults


def _clear_cache(parent):
	if frappe.flags.in_install:
		return
	frappe.clear_cache(user=parent if parent not in common_default_keys else None)
