# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.website.permissions import get_access
from frappe.utils.email_lib.bulk import send

@frappe.whitelist()
def suggest_user(term, group):
	doc = frappe.get_doc("Website Group", group)
	pathname = doc.get_route()
	if not get_access(doc, pathname).get("admin"):
		raise frappe.PermissionError

	users = frappe.db.sql("""select pr.name, pr.first_name, pr.last_name,
		pr.user_image, pr.location
		from `tabUser` pr
		where (pr.first_name like %(term)s or pr.last_name like %(term)s)
		and pr.user_type = "Website User"
		and pr.user_image is not null and pr.enabled=1
		and not exists(select wsp.name from `tabWebsite Route Permission` wsp
			where wsp.website_route=%(group)s and wsp.user=pr.name)""",
		{"term": "%{}%".format(term), "group": pathname}, as_dict=True)

	template = frappe.get_template("templates/includes/user_display.html")
	return [{
		"value": "{} {}".format(pr.first_name or "", pr.last_name or ""),
		"user_html": template.render({"user": pr}),
		"user": pr.name
	} for pr in users]

@frappe.whitelist()
def add_sitemap_permission(group, user):
	doc = frappe.get_doc("Website Group", group)
	pathname = doc.get_route()
	if not get_access(doc, pathname).get("admin"):
		raise frappe.PermissionError

	permission = frappe.get_doc({
		"doctype": "Website Route Permission",
		"website_route": pathname,
		"user": user,
		"read": 1
	})
	permission.insert(ignore_permissions=True)

	user = permission.as_dict()
	user.update(frappe.db.get_value("User", user.user,
		["name", "first_name", "last_name", "user_image", "location"], as_dict=True))

	return frappe.get_template("templates/includes/sitemap_permission.html").render({
		"user": user
	})

@frappe.whitelist()
def update_permission(group, user, perm, value):
	doc = frappe.get_doc("Website Group", group)
	pathname = doc.get_route()
	if not get_access(doc, pathname).get("admin"):
		raise frappe.PermissionError

	permission = frappe.get_doc("Website Route Permission",
		{"website_route": pathname, "user": user, "reference": group})
	permission.set(perm, int(value))
	permission.save(ignore_permissions=True)

	# send email
	if perm=="admin" and int(value):
		subject = "You have been made Administrator of Group " + doc.group_title

		send(recipients=[user],
			subject= subject, add_unsubscribe_link=False,
			message="""<h3>Group Notification<h3>\
			<p>%s</p>\
			<p style="color: #888">This is just for your information.</p>""" % subject)

@frappe.whitelist()
def update_description(group, description):
	doc = frappe.get_doc("Website Group", group)
	pathname = doc.get_route()
	if not get_access(doc, pathname).get("admin"):
		raise frappe.PermissionError

	group = frappe.get_doc("Website Group", group)
	group.group_description = description
	group.save(ignore_permissions=True)

@frappe.whitelist()
def add_website_group(group, new_group, public_read, public_write, group_type="Forum"):
	doc = frappe.get_doc("Website Group", group)
	pathname = doc.get_route()
	if not get_access(doc, pathname).get("admin"):
		raise frappe.PermissionError

	frappe.get_doc({
		"doctype": "Website Group",
		"group_name": group + "-" + new_group,
		"group_title": new_group,
		"parent_website_group": group,
		"group_type": group_type,
		"public_read": int(public_read),
		"public_write": int(public_write)
	}).insert(ignore_permissions=True)
