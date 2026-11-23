import frappe
from frappe.core.utils import html_to_plain_text
from frappe.utils import create_batch


def execute():
	nl = frappe.qb.DocType("Notification Log")
	names = (
		frappe.qb.from_(nl)
		.select(nl.name)
		.where((nl.description == nl.email_content) & nl.email_content.like("%<%"))
		.run(pluck=True)
	)
	for batch in create_batch(names, 1000):
		rows = frappe.get_all(
			"Notification Log",
			filters={"name": ("in", batch)},
			fields=["name", "email_content"],
			as_list=True,
		)
		frappe.db.bulk_update(
			"Notification Log",
			{name: {"description": html_to_plain_text(content)} for name, content in rows},
			update_modified=False,
		)
