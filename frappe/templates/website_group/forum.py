# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import now_datetime, get_datetime_str
from frappe.website.permissions import get_access

@frappe.whitelist(allow_guest=True)
def get_post_list_html(group, view, limit_start=0, limit_length=20):
	from frappe.website.doctype.website_group.website_group import get_views

	# verify permission for paging
	if frappe.local.form_dict.cmd == "get_post_list_html":
		doc = frappe.get_doc("Website Group", group)
		access = get_access(doc, doc.get_route())

		if not access.get("read"):
			return frappe.PermissionError

	conditions = ""
	values = [group]

	group_type = frappe.db.get_value("Website Group", group, "group_type")
	if group_type == "Events":
		# should show based on time upto precision of hour
		# because the current hour should also be in upcoming
		values.append(now_datetime().replace(minute=0, second=0, microsecond=0))

	if view in ("feed", "closed"):
		order_by = "p.creation desc"

		if view == "closed":
			conditions += " and p.is_task=1 and p.status='Closed'"

	elif view in ("popular", "open"):
		now = get_datetime_str(now_datetime())
		order_by = """(p.upvotes + post_reply_count - (timestampdiff(hour, p.creation, \"{}\") / 2)) desc,
			p.creation desc""".format(now)

		if view == "open":
			conditions += " and p.is_task=1 and p.status='Open'"

	elif view == "upcoming":
		conditions += " and p.is_event=1 and p.event_datetime >= %s"
		order_by = "p.event_datetime asc"

	elif view == "past":
		conditions += " and p.is_event=1 and p.event_datetime < %s"
		order_by = "p.event_datetime desc"

	values += [int(limit_start), int(limit_length)]

	posts = frappe.db.sql("""select p.*, pr.user_image, pr.first_name, pr.last_name,
		(select count(pc.name) from `tabPost` pc where pc.parent_post=p.name) as post_reply_count
		from `tabPost` p, `tabUser` pr
		where p.website_group = %s and pr.name = p.owner and ifnull(p.parent_post, '')=''
		{conditions} order by {order_by} limit %s, %s""".format(conditions=conditions, order_by=order_by),
		tuple(values), as_dict=True)

	context = { "posts": posts, "limit_start": limit_start, "view": get_views(group_type)[view] }

	return frappe.get_template("templates/includes/post_list.html").render(context)

