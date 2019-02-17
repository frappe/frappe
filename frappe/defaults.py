# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.desk.notifications import clear_notifications
from frappe.cache_manager import clear_defaults_cache, common_default_keys

# Note: DefaultValue records are identified by parenttype
# __default, __global or 'User Permission'

def set_user_default(key, value, user=None, parenttype=None):
	set_default(key, value, user or frappe.session.user, parenttype)

def add_user_default(key, value, user=None, parenttype=None):
	add_default(key, value, user or frappe.session.user, parenttype)

def get_user_default(key, user=None):
	user_defaults = get_defaults(user or frappe.session.user)
	d = user_defaults.get(key, None)

	if is_a_user_permission_key(key):
		if d and isinstance(d, (list, tuple)) and len(d)==1:
			# Use User Permission value when only when it has a single value
			d = d[0]

		else:
			d = user_defaults.get(frappe.scrub(key), None)

	value = isinstance(d, (list, tuple)) and d[0] or d
	if not_in_user_permission(key, value, user):
		return

	return value

def get_user_default_as_list(key, user=None):
	user_defaults = get_defaults(user or frappe.session.user)
	d = user_defaults.get(key, None)

	if is_a_user_permission_key(key):
		if d and isinstance(d, (list, tuple)) and len(d)==1:
			# Use User Permission value when only when it has a single value
			d = [d[0]]

		else:
			d = user_defaults.get(frappe.scrub(key), None)

	d = list(filter(None, (not isinstance(d, (list, tuple))) and [d] or d))

	# filter default values if not found in user permission
	values = [value for value in d if not not_in_user_permission(key, value)]

	return values

def is_a_user_permission_key(key):
	return ":" not in key and key != frappe.scrub(key)

def not_in_user_permission(key, value, user=None):
	# returns true or false based on if value exist in user permission
	user = user or frappe.session.user
	user_permission = get_user_permissions(user).get(frappe.unscrub(key)) or []

	for perm in user_permission:
		# doc found in user permission
		if perm.get('doc') == value: return False

	# return true only if user_permission exists
	return True if user_permission else False

def get_user_permissions(user=None):
	from frappe.core.doctype.user_permission.user_permission \
		import get_user_permissions as _get_user_permissions
	'''Return frappe.core.doctype.user_permissions.user_permissions._get_user_permissions (kept for backward compatibility)'''
	return _get_user_permissions(user)

def get_defaults(user=None):
	globald = get_defaults_for()

	if not user:
		user = frappe.session.user if frappe.session else "Guest"

	if user:
		userd = {}
		userd.update(get_defaults_for(user))
		userd.update({"user": user, "owner": user})
		globald.update(userd)

	return globald

def clear_user_default(key, user=None):
	clear_default(key, parent=user or frappe.session.user)

# Global

def set_global_default(key, value):
	set_default(key, value, "__default")

def add_global_default(key, value):
	add_default(key, value, "__default")

def get_global_default(key):
	d = get_defaults().get(key, None)

	value = isinstance(d, (list, tuple)) and d[0] or d
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
	if frappe.db.sql('''
		select
			defkey
		from
			`tabDefaultValue`
		where
			defkey=%s and parent=%s
		for update''', (key, parent)):
		frappe.db.sql("""
			delete from
				`tabDefaultValue`
			where
				defkey=%s and parent=%s""", (key, parent))
	if value != None:
		add_default(key, value, parent)
	else:
		_clear_cache(parent)

def add_default(key, value, parent, parenttype=None):
	d = frappe.get_doc({
		"doctype": "DefaultValue",
		"parent": parent,
		"parenttype": parenttype or "__default",
		"parentfield": "system_defaults",
		"defkey": key,
		"defvalue": value
	})
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
	conditions = []
	values = []

	if name:
		conditions.append("name=%s")
		values.append(name)

	else:
		if key:
			conditions.append("defkey=%s")
			values.append(key)

		if value:
			conditions.append("defvalue=%s")
			values.append(value)

		if parent:
			conditions.append("parent=%s")
			values.append(parent)

		if parenttype:
			conditions.append("parenttype=%s")
			values.append(parenttype)

	if parent:
		clear_defaults_cache(parent)
	else:
		clear_defaults_cache("__default")
		clear_defaults_cache("__global")

	if not conditions:
		raise Exception("[clear_default] No key specified.")

	frappe.db.sql("""delete from tabDefaultValue where {0}""".format(" and ".join(conditions)),
		tuple(values))

	_clear_cache(parent)

def get_defaults_for(parent="__default"):
	"""get all defaults"""
	defaults = frappe.cache().hget("defaults", parent)

	if defaults==None:
		# sort descending because first default must get precedence
		res = frappe.db.sql("""select defkey, defvalue from `tabDefaultValue`
			where parent = %s order by creation""", (parent,), as_dict=1)

		defaults = frappe._dict({})
		for d in res:
			if d.defkey in defaults:
				# listify
				if not isinstance(defaults[d.defkey], list) and defaults[d.defkey] != d.defvalue:
					defaults[d.defkey] = [defaults[d.defkey]]

				if d.defvalue not in defaults[d.defkey]:
					defaults[d.defkey].append(d.defvalue)

			elif d.defvalue is not None:
				defaults[d.defkey] = d.defvalue

		frappe.cache().hset("defaults", parent, defaults)

	return defaults

def _clear_cache(parent):
	if parent in common_default_keys:
		frappe.clear_cache()
	else:
		clear_notifications(user=parent)
		frappe.clear_cache(user=parent)
