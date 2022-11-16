# Copyright (c) 2021, FOSS United and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.realtime import get_website_room


class DiscussionReply(Document):
	def after_insert(self):

		replies = frappe.db.count("Discussion Reply", {"topic": self.topic})
		template = frappe.render_template(
			"frappe/templates/discussions/reply_card.html",
			{"reply": self, "topic": {"name": self.topic}, "loop": {"index": replies}},
		)

		topic_info = frappe.get_all(
			"Discussion Topic",
			{"name": self.topic},
			["reference_doctype", "reference_docname", "name", "title", "owner", "creation"],
		)

		sidebar = frappe.render_template(
			"frappe/templates/discussions/sidebar.html", {"topic": topic_info[0]}
		)

		new_topic_template = frappe.render_template(
			"frappe/templates/discussions/reply_section.html", {"topics": topic_info}
		)

		frappe.publish_realtime(
			event="publish_message",
			room=get_website_room(),
			message={
				"template": template,
				"topic_info": topic_info[0],
				"sidebar": sidebar,
				"new_topic_template": new_topic_template,
			},
			after_commit=True,
		)
