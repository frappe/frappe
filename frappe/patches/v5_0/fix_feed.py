from __future__ import unicode_literals
import frappe

def execute():
	frappe.reload_doc("desk", "doctype", "feed")

	for feed in frappe.db.sql("select name from `tabFeed` where doc_type='Comment'", as_dict=True):
		feed = frappe.get_doc("Feed", feed)
		comment = frappe.get_doc(feed.doc_type, feed.doc_name)
		new_feed = comment.get_feed()

		if not new_feed:
			frappe.db.sql("delete from `tabFeed` where name=%s", feed.name)
			continue

		feed.subject = new_feed["subject"]
		feed.doc_type = new_feed["doctype"]
		feed.doc_name = new_feed["name"]
		feed.feed_type = new_feed["feed_type"]
		feed.save()
