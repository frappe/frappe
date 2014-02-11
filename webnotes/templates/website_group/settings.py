# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
from webnotes.webutils import get_access, clear_permissions
from webnotes.templates.generators.website_group import get_pathname
from webnotes.utils.email_lib.bulk import send

@webnotes.whitelist()
def suggest_user(term, group):
	pathname = get_pathname(group)
	if not get_access(pathname).get("admin"):
		raise webnotes.PermissionError
		
	profiles = webnotes.conn.sql("""select pr.name, pr.first_name, pr.last_name, 
		pr.user_image, pr.location
		from `tabProfile` pr 
		where (pr.first_name like %(term)s or pr.last_name like %(term)s)
		and pr.user_type = "Website User"
		and pr.user_image is not null and pr.enabled=1
		and not exists(select wsp.name from `tabWebsite Sitemap Permission` wsp 
			where wsp.website_sitemap=%(group)s and wsp.profile=pr.name)""", 
		{"term": "%{}%".format(term), "group": pathname}, as_dict=True)
	
	template = webnotes.get_template("templates/includes/profile_display.html")
	return [{
		"value": "{} {}".format(pr.first_name or "", pr.last_name or ""),
		"profile_html": template.render({"profile": pr}),
		"profile": pr.name
	} for pr in profiles]

@webnotes.whitelist()
def add_sitemap_permission(group, profile):
	pathname = get_pathname(group)
	if not get_access(pathname).get("admin"):
		raise webnotes.PermissionError
		
	permission = webnotes.bean({
		"doctype": "Website Sitemap Permission",
		"website_sitemap": pathname,
		"profile": profile,
		"read": 1
	})
	permission.insert(ignore_permissions=True)
	
	profile = permission.doc.fields
	profile.update(webnotes.conn.get_value("Profile", profile.profile, 
		["name", "first_name", "last_name", "user_image", "location"], as_dict=True))
	
	return webnotes.get_template("templates/includes/sitemap_permission.html").render({
		"profile": profile
	})

@webnotes.whitelist()
def update_permission(group, profile, perm, value):
	pathname = get_pathname(group)
	if not get_access(pathname).get("admin"):
		raise webnotes.PermissionError
		
	permission = webnotes.bean("Website Sitemap Permission", {"website_sitemap": pathname, "profile": profile})
	permission.doc.fields[perm] = int(value)
	permission.save(ignore_permissions=True)
	
	# send email
	if perm=="admin" and int(value):
		group_title = webnotes.conn.get_value("Website Sitemap", pathname, "page_title")
		
		subject = "You have been made Administrator of Group " + group_title
		
		send(recipients=[profile], 
			subject= subject, add_unsubscribe_link=False,
			message="""<h3>Group Notification<h3>\
			<p>%s</p>\
			<p style="color: #888">This is just for your information.</p>""" % subject)

@webnotes.whitelist()
def update_description(group, description):
	if not get_access(get_pathname(group)).get("admin"):
		raise webnotes.PermissionError

	group = webnotes.bean("Website Group", group)
	group.doc.group_description = description
	group.save(ignore_permissions=True)
	
@webnotes.whitelist()
def add_website_group(group, new_group, public_read, public_write, group_type="Forum"):
	if not get_access(get_pathname(group)).get("admin"):
		raise webnotes.PermissionError
		
	parent_website_sitemap = webnotes.conn.get_value("Website Sitemap", 
		{"ref_doctype": "Website Group", "docname": group})
	
	webnotes.bean({
		"doctype": "Website Group",
		"group_name": group + "-" + new_group,
		"group_title": new_group,
		"parent_website_sitemap": parent_website_sitemap,
		"group_type": group_type,
		"public_read": int(public_read),
		"public_write": int(public_write)
	}).insert(ignore_permissions=True)