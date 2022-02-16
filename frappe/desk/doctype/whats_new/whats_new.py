# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class WhatsNew(Document):

	def on_save(self):
		if self.post_type == "Version Update":
			self.event_date = self.posting_date

	pass



@frappe.whitelist(allow_guest=True)
def fetch_latest_posts():
	post_list = []
	event_list = []
	fields = ["name", "title", "description", "banner", "post_type", "posting_date", "source_link", "event_date", "event_time"]
	try:
		posts = frappe.get_all("Whats New", fields=fields, filters={"docstatus":1},order_by="event_date desc")
	except:
		traceback = frappe.get_traceback()
		frappe.log_error(title=frappe._("Error while retrieving posts"), message=traceback)

	for post in posts:
		try:
			tags = frappe.get_all("Whats New Tag", filters={"parent":post.name}, fields=["tag"])
		except:
			traceback = frappe.get_traceback()
			frappe.log_error(title=frappe._("Error while retrieving tags for posts"), message=traceback)

		if tags:
			post.tags = tags

		if post.post_type == "Version Update":
			post_list.append(post)
		else:
			event_list.append(post)

	return post_list, event_list
