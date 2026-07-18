# Copyright (c) 2021, FOSS United and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class DiscussionTopic(Document):
	_DOCTYPE_NAME = "Discussion Topic"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		reference_docname: DF.DynamicLink | None
		reference_doctype: DF.Link | None
		title: DF.Data | None
	# end: auto-generated types

	pass


def save_message(reply, topic):
	frappe.get_doc({"doctype": "Discussion Reply", "reply": reply, "topic": topic}).save(
		ignore_permissions=True
	)


# `submit_discussion` moved to frappe.website.api. The aliases keep the old
# dotted paths working; resolved lazily to avoid circular imports.
_MOVED_TO_WEBSITE_API = {
	"submit_discussion": "submit_discussion",
}


def __getattr__(name: str):
	if new_name := _MOVED_TO_WEBSITE_API.get(name):
		from frappe.website import api

		return getattr(api, new_name)
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
