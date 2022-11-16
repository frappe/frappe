# Copyright (c) 2021, FOSS United and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class DiscussionReply(Document):
<<<<<<< HEAD
=======
	def on_update(self):
		frappe.publish_realtime(
			event="update_message",
			room="website",
			message={"reply": frappe.utils.md_to_html(self.reply), "reply_name": self.name},
			after_commit=True,
		)

>>>>>>> 96fee8c293 (feat: {site}:website room open to all users)
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
			room="website",
			message={
				"template": template,
				"topic_info": topic_info[0],
				"sidebar": sidebar,
				"new_topic_template": new_topic_template,
			},
			after_commit=True,
		)
<<<<<<< HEAD
=======

	def after_delete(self):
		frappe.publish_realtime(
			event="delete_message", room="website", message={"reply_name": self.name}, after_commit=True
		)


@frappe.whitelist()
def delete_message(reply_name):
	frappe.delete_doc("Discussion Reply", reply_name, ignore_permissions=True)
>>>>>>> 96fee8c293 (feat: {site}:website room open to all users)
