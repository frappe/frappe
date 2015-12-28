# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cint
from frappe.desk.doctype.feed.feed import get_permission_query_conditions

@frappe.whitelist()
def get_feed(limit_start, limit_page_length, show_likes=False):
	"""get feed"""
	# directly use the permission query condition function of feed
	match_conditions = get_permission_query_conditions(frappe.session.user)

	result = frappe.db.sql("""select name, feed_type, doc_type, doc_name, subject,
			owner, modified, creation, seen, reference_doctype, reference_name
		from `tabFeed`
		where
			((feed_type='Like' and (owner=%(user)s or doc_owner=%(user)s)) or feed_type!='Like')
			{match_conditions}
			{show_likes}
		order by creation desc
		limit %(limit_start)s, %(limit_page_length)s"""
		.format(match_conditions="and {0}".format(match_conditions) if match_conditions else "",
			show_likes="and feed_type='Like'" if show_likes else ""),
		{
			"user": frappe.session.user,
			"limit_start": cint(limit_start),
			"limit_page_length": cint(limit_page_length)
		}, as_dict=True)

	if show_likes:
		# mark likes as seen!
		frappe.db.sql("update `tabFeed` set seen=1 where feed_type='Like' and doc_owner=%s", frappe.session.user)
		frappe.local.flags.commit = True

	return result

@frappe.whitelist()
def get_months_activity():
	return frappe.db.sql("""select date(creation), count(name)
		from `tabFeed` where date(creation) > subdate(curdate(), interval 1 month)
		group by date(creation)
		order by creation asc""", as_list=1)
