# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cint
from frappe.core.doctype.communication.feed import get_feed_match_conditions

@frappe.whitelist()
def get_feed(start, page_length, show_likes=False):
	"""get feed"""
	match_conditions = get_feed_match_conditions(frappe.session.user)

	result = frappe.db.sql("""select name, owner, modified, creation, seen, comment_type,
			reference_doctype, reference_name, link_doctype, link_name, subject,
			communication_type, communication_medium, content
		from `tabCommunication`
		where
			communication_type in ("Communication", "Comment")
			and communication_medium != "Email"
			and (comment_type is null or comment_type != "Like"
				or (comment_type="Like" and (owner=%(user)s or reference_owner=%(user)s)))
			{match_conditions}
			{show_likes}
		order by creation desc
		limit %(start)s, %(page_length)s"""
		.format(match_conditions="and {0}".format(match_conditions) if match_conditions else "",
			show_likes="and comment_type='Like'" if show_likes else ""),
		{
			"user": frappe.session.user,
			"start": cint(start),
			"page_length": cint(page_length)
		}, as_dict=True)

	if show_likes:
		# mark likes as seen!
		frappe.db.sql("""update `tabCommunication` set seen=1
			where comment_type='Like' and reference_owner=%s""", frappe.session.user)
		frappe.local.flags.commit = True

	return result

@frappe.whitelist()
def get_heatmap_data():
	return dict(frappe.db.sql("""select unix_timestamp(date(creation)), count(name)
		from `tabCommunication`
		where
			communication_type in ("Communication", "Comment")
			and communication_medium != "Email"
			and date(creation) > subdate(curdate(), interval 1 year)
		group by date(creation)
		order by creation asc"""))