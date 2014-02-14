# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe


def remove_empty_permissions():
	permissions_cache_to_be_cleared = frappe.conn.sql_list("""select distinct profile 
		from `tabWebsite Sitemap Permission`
		where ifnull(`read`, 0)=0 and ifnull(`write`, 0)=0 and ifnull(`admin`, 0)=0""")
	
	frappe.conn.sql("""delete from `tabWebsite Sitemap Permission`
		where ifnull(`read`, 0)=0 and ifnull(`write`, 0)=0 and ifnull(`admin`, 0)=0""")
		
	clear_permissions(permissions_cache_to_be_cleared)

def get_access(sitemap_page, profile=None):
	profile = profile or frappe.session.user
	key = "website_sitemap_permissions:{}".format(profile)
	
	cache = frappe.cache()
	permissions = cache.get_value(key) or {}
	if not permissions.get(sitemap_page):
		permissions[sitemap_page] = _get_access(sitemap_page, profile)
		cache.set_value(key, permissions)
		
	return permissions.get(sitemap_page)
	
def _get_access(sitemap_page, profile):
	lft, rgt, public_read, public_write = frappe.conn.get_value("Website Sitemap", sitemap_page, 
		["lft", "rgt", "public_read", "public_write"])

	if not (lft and rgt):
		raise frappe.ValidationError("Please rebuild Website Sitemap Tree")
		
	if profile == "Guest":
		return { "read": public_read, "write": 0, "admin": 0 }
		
	read = write = admin = private_read = 0

	if public_write:
		read = write = 1
	elif public_read:
		read = 1

	for perm in frappe.conn.sql("""select wsp.`read`, wsp.`write`, wsp.`admin`, 
		ws.lft, ws.rgt, ws.name
		from `tabWebsite Sitemap Permission` wsp, `tabWebsite Sitemap` ws
		where wsp.profile = %s and wsp.website_sitemap = ws.name 
		order by lft asc""", (profile,), as_dict=True):
		if perm.lft <= lft and perm.rgt >= rgt:
			if not (public_read or private_read): private_read = perm.read
			if not read: read = perm.read
			if not write: write = perm.write
			if not admin: admin = perm.admin
			if write: read = write
	
			if read and write and admin:
				break

	return { "read": read, "write": write, "admin": admin, "private_read": private_read }

def clear_permissions(profiles=None):
	if isinstance(profiles, basestring):
		profiles = [profiles]
	elif profiles is None:
		profiles = frappe.conn.sql_list("""select name from `tabProfile`""")
	
	cache = frappe.cache()
	for profile in profiles:
		cache.delete_value("website_sitemap_permissions:{}".format(profile))
