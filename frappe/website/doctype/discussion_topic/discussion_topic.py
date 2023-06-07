# Copyright (c) 2021, FOSS United and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class DiscussionTopic(Document):
	pass


@frappe.whitelist()
def submit_discussion(doctype, docname, reply, title, topic_name=None, reply_name=None):

	if reply_name:
		doc = frappe.get_doc("Discussion Reply", reply_name)
		doc.reply = reply
		doc.save(ignore_permissions=True)
		return

	if topic_name:
		save_message(reply, topic_name)
		return topic_name

	topic = frappe.get_doc(
		{
			"doctype": "Discussion Topic",
			"title": title,
			"reference_doctype": doctype,
			"reference_docname": docname,
		}
	)
	topic.save(ignore_permissions=True)
	save_message(reply, topic.name)
	return topic.name


def save_message(reply, topic):
	frappe.get_doc({"doctype": "Discussion Reply", "reply": reply, "topic": topic}).save(
		ignore_permissions=True
	)
