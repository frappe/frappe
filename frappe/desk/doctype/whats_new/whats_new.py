# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class WhatsNew(Document):
	pass

@frappe.whitelist(allow_guest=True)
def fetch_latest_posts():
	fields = ["name", "title", "description", "banner", "post_type", "posting_date", "source_link", "tags"]
	posts = frappe.get_all("Whats New", fields=fields)
	for post in posts:
		tags = frappe.get_all("Whats New Tag", filters={"parent":post.name}, fields=["tag"])
		if tags:
			post.tags = tags

	print("POSTS HERE",posts)
	return posts
