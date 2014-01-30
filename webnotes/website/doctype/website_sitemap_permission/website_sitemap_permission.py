# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
	def on_update(self):
		remove_empty_permissions()
		
def remove_empty_permissions():
	permissions_cache_to_be_cleared = webnotes.conn.sql_list("""select distinct profile 
		from `tabWebsite Sitemap Permission`
		where ifnull(`read`, 0)=0 and ifnull(`write`, 0)=0 and ifnull(`admin`, 0)=0""")
	
	webnotes.conn.sql("""delete from `tabWebsite Sitemap Permission`
		where ifnull(`read`, 0)=0 and ifnull(`write`, 0)=0 and ifnull(`admin`, 0)=0""")
		
	clear_permissions(permissions_cache_to_be_cleared)

def get_access(website_node, profile=None):
	profile = profile or webnotes.session.user
	key = "website_sitemap_permissions:{}".format(profile)
	
	cache = webnotes.cache()
	permissions = cache.get_value(key) or {}
	if not permissions.get(website_node):
		permissions[website_node] = _get_access(website_node, profile)
		cache.set_value(key, permissions)
		
	return permissions.get(website_node)
	
def _get_access(website_node, profile):
	lft, rgt, public_read, public_write = webnotes.conn.get_value("Website Sitemap", website_node, 
		["lft", "rgt", "public_read", "public_write"])

	if not (lft and rgt):
		raise webnotes.ValidationError("Please rebuild Website Sitemap Tree")
		
	if profile == "Guest":
		return { "read": public_read, "write": 0, "admin": 0 }
		
	read = write = admin = private_read = 0

	if public_write:
		read = write = 1
	elif public_read:
		read = 1

	for perm in webnotes.conn.sql("""select wsp.`read`, wsp.`write`, wsp.`admin`, 
		ws.lft, ws.rgt, ws.name
		from `tabWebsite Sitemap Permission` up, `tabWebsite Sitemap` ws
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

def clear_permissions(profiles):
	if isinstance(profiles, basestring):
		profiles = [profiles]
	
	cache = webnotes.cache()
	for profile in profiles:
		cache.delete_value("website_sitemap_permissions:{}".format(profile))
