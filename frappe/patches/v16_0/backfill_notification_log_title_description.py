import frappe


def execute():
	"""Backfill Notification Log so Title/Description and the email Subject/Email Content
	are mirrored on existing rows (matches NotificationLog.before_insert).

	Older rows only have Subject/Email Content; rows created by the new System Notification
	path only have Title/Description (Subject is now optional). Fill each side from the other
	so both bells render and the email path never sees a null subject.
	"""
	frappe.reload_doctype("Notification Log")

	nl = frappe.qb.DocType("Notification Log")

	def _empty(col):
		return col.isnull() | (col == "")

	# title <-> subject
	frappe.qb.update(nl).set(nl.title, nl.subject).where(_empty(nl.title) & nl.subject.isnotnull()).run()
	frappe.qb.update(nl).set(nl.subject, nl.title).where(_empty(nl.subject) & nl.title.isnotnull()).run()

	# description <-> email_content
	frappe.qb.update(nl).set(nl.description, nl.email_content).where(
		_empty(nl.description) & nl.email_content.isnotnull()
	).run()
	frappe.qb.update(nl).set(nl.email_content, nl.description).where(
		_empty(nl.email_content) & nl.description.isnotnull()
	).run()
