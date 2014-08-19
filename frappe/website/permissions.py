# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def remove_empty_permissions():
	permissions_cache_to_be_cleared = frappe.db.sql_list("""select distinct user
		from `tabWebsite Route Permission`
		where ifnull(`read`, 0)=0 and ifnull(`write`, 0)=0 and ifnull(`admin`, 0)=0""")

	frappe.db.sql("""delete from `tabWebsite Route Permission`
		where ifnull(`read`, 0)=0 and ifnull(`write`, 0)=0 and ifnull(`admin`, 0)=0""")

	clear_permissions(permissions_cache_to_be_cleared)

def get_access(doc, pathname, user=None):
	user = user or frappe.session.user
	key = "website_route_permissions:{}".format(user)

	cache = frappe.cache()
	permissions = cache.get_value(key) or {}
	if not permissions.get(doc.name):
		permissions[doc.name] = _get_access(doc, pathname, user)
		cache.set_value(key, permissions)

	return permissions.get(doc.name)

def _get_access(doc, pathname, user):
	read = write = admin = private_read = 0

	if user == "Guest":
		return { "read": doc.public_read, "write": 0, "admin": 0 }

	if doc.public_write:
		read = write = 1
	elif doc.public_read:
		read = 1

	for perm in frappe.db.sql("""select
			`tabWebsite Route Permission`.`read`,
			`tabWebsite Route Permission`.`write`,
			`tabWebsite Route Permission`.`admin`,
			`tabWebsite Group`.lft,
			`tabWebsite Group`.rgt
		from
			`tabWebsite Route Permission`, `tabWebsite Group`
		where
			`tabWebsite Route Permission`.website_route = %s and
			`tabWebsite Route Permission`.user = %s and
			`tabWebsite Route Permission`.reference = `tabWebsite Group`.name
		order by `tabWebsite Group`.lft asc""", (user, pathname), as_dict=True):
		if perm.lft <= doc.lft and perm.rgt >= doc.rgt:
			if not (doc.public_read or private_read):
				private_read = perm.read
			if not read: read = perm.read
			if not write: write = perm.write
			if not admin: admin = perm.admin
			if write: read = write

		if read and write and admin:
			break

	else:
		read = write = admin = private_read = 1

	return { "read": read, "write": write, "admin": admin, "private_read": private_read }

def clear_permissions(users=None):
	if isinstance(users, basestring):
		users = [users]
	elif users is None:
		users = frappe.db.sql_list("""select name from `tabUser`""")

	cache = frappe.cache()
	for user in users:
		cache.delete_value("website_route_permissions:{}".format(user))
