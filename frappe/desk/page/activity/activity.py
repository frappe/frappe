# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cint
from frappe.core.doctype.activity_log.feed import get_feed_match_conditions

@frappe.whitelist()
def get_feed(start, page_length):
	"""get feed"""
	match_conditions_communication = get_feed_match_conditions(frappe.session.user, 'Communication')
	match_conditions_comment = get_feed_match_conditions(frappe.session.user, 'Comment')

	result = frappe.db.sql("""select X.*
		from (select `tabCommunication`.name, `tabCommunication`.owner, `tabCommunication`.modified,
				`tabCommunication`.creation, `tabCommunication`.seen, `tabCommunication`.comment_type,
				`tabCommunication`.reference_doctype, `tabCommunication`.reference_name, `tabCommunication`.subject,
				`tabCommunication`.communication_type, `tabCommunication`.communication_medium, `tabCommunication`.content,
				`tabCommunication Link`.link_doctype, `tabCommunication Link`.link_name
			from
				`tabCommunication`
					inner join `tabCommunication Link`
						on `tabCommunication`.name=`tabCommunication Link`.parent
			where
				`tabCommunication`.communication_type = "Communication"
				and `tabCommunication`.communication_medium != "Email"
				and {match_conditions_communication}
		UNION
			select name, owner, modified, creation, '0', 'Updated',
				reference_doctype, reference_name, link_doctype, link_name, subject,
				'Comment', '', content
			from
				`tabActivity Log`
		UNION
			select name, owner, modified, creation, '0', comment_type,
				reference_doctype, reference_name, link_doctype, link_name, '',
				'Comment', '', content
			from
				`tabComment`
			where
				{match_conditions_comment}
		) X
		order by X.creation DESC
		LIMIT %(page_length)s
		OFFSET %(start)s"""
		.format(match_conditions_comment = match_conditions_comment,
			match_conditions_communication = match_conditions_communication), {
			"user": frappe.session.user,
			"start": cint(start),
			"page_length": cint(page_length)
		}, as_dict=True)

	return result

@frappe.whitelist()
def get_heatmap_data():
	return dict(frappe.db.sql("""select unix_timestamp(date(creation)), count(name)
		from `tabActivity Log`
		where
			date(creation) > subdate(curdate(), interval 1 year)
		group by date(creation)
		order by creation asc"""))
