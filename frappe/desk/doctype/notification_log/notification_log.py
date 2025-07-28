# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.desk.doctype.notification_settings.notification_settings import (
	is_email_notifications_enabled_for_type,
	is_notifications_enabled,
)
from frappe.model.document import Document
from frappe.utils.caching import http_cache


class NotificationLog(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		attached_file: DF.Code | None
		document_name: DF.Data | None
		document_type: DF.Link | None
		email_content: DF.TextEditor | None
		email_header: DF.Data | None
		for_user: DF.Link | None
		from_user: DF.Link | None
		link: DF.SmallText | None
		read: DF.Check
		subject: DF.Text | None
		type: DF.Literal["", "Mention", "Assignment", "Share", "Alert"]
	# end: auto-generated types

	def after_insert(self):
		frappe.publish_realtime("notification", after_commit=True, user=self.for_user)
		set_notifications_as_unseen(self.for_user)
		if is_email_notifications_enabled_for_type(self.for_user, self.type):
			try:
				send_notification_email(self)
			except frappe.OutgoingEmailError:
				self.log_error(_("Failed to send notification email"))

	@staticmethod
	def clear_old_logs(days=180):
		from frappe.query_builder import Interval
		from frappe.query_builder.functions import Now

		table = frappe.qb.DocType("Notification Log")
		frappe.db.delete(table, filters=(table.creation < (Now() - Interval(days=days))))


def get_permission_query_conditions(for_user):
	if not for_user:
		for_user = frappe.session.user

	if for_user == "Administrator":
		return

	return f"""(`tabNotification Log`.for_user = {frappe.db.escape(for_user)})"""


def get_title(doctype, docname, title_field=None):
	if not title_field:
		title_field = frappe.get_meta(doctype).get_title_field()
	return docname if title_field == "name" else frappe.db.get_value(doctype, docname, title_field)


def get_title_html(title):
	return f'<b class="subject-title">{title}</b>'


def enqueue_create_notification(users: list[str] | str, doc: dict):
	"""Send notification to users.

	users: list of user emails or string of users with comma separated emails
	doc: contents of `Notification` doc
	"""

	# During installation of new site, enqueue_create_notification tries to connect to Redis.
	# This breaks new site creation if Redis server is not running.
	# We do not need any notifications in fresh installation
	if frappe.flags.in_install:
		return

	doc = frappe._dict(doc)

	if isinstance(users, str):
		users = [user.strip() for user in users.split(",") if user.strip()]
	users = list(set(users))

	frappe.enqueue(
		"frappe.desk.doctype.notification_log.notification_log.make_notification_logs",
		doc=doc,
		users=users,
		now=frappe.in_test,
		enqueue_after_commit=not frappe.in_test,
	)


def make_notification_logs(doc, users):
	for user in _get_user_ids(users):
		notification = frappe.new_doc("Notification Log")
		notification.update(doc)
		notification.for_user = user
		if notification.for_user != notification.from_user or doc.type == "Alert":
			notification.insert(ignore_permissions=True)


def _get_user_ids(user_emails):
	user_names = frappe.db.get_values(
		"User", {"enabled": 1, "email": ("in", user_emails)}, "name", pluck=True
	)
	return [user for user in user_names if is_notifications_enabled(user)]


def send_notification_email(doc: NotificationLog):
	from frappe.utils import get_url_to_form, strip_html

	user = frappe.db.get_value("User", doc.for_user, fieldname=["email", "language"], as_dict=True)
	if not user:
		return

	header = get_email_header(doc, user.language)
	email_subject = strip_html(doc.subject)
	args = {
		"body_content": doc.subject,
		"description": doc.email_content,
	}
	if doc.link:
		args["doc_link"] = doc.link
	else:
		args["document_type"] = doc.document_type
		args["document_name"] = doc.document_name
		args["doc_link"] = get_url_to_form(doc.document_type, doc.document_name)

	frappe.sendmail(
		recipients=user.email,
		subject=email_subject,
		template="new_notification",
		args=args,
		header=[header, "orange"],
		now=frappe.in_test,
	)


def get_email_header(doc, language: str | None = None):
	docname = doc.document_name
	header_map = {
		"Default": _("New Notification", lang=language),
		"Mention": _("New Mention on {0}", lang=language).format(docname),
		"Assignment": _("Assignment Update on {0}", lang=language).format(docname),
		"Share": _("New Document Shared {0}", lang=language).format(docname),
	}
	if not doc.email_header:
		doc.email_header = header_map[doc.type or "Default"]
	return doc.email_header


def format_email_header(header_map, language, docname):
	messages = []
	for v in list(header_map.values()):
		messages.append(_(v[0], lang=language).format(docname))
	return dict(zip(header_map.keys(), messages, strict=True))


@frappe.whitelist()
@http_cache(max_age=60, stale_while_revalidate=60 * 60)
def get_notification_logs(limit=20):
	notification_logs = frappe.db.get_list(
		"Notification Log", fields=["*"], limit=limit, order_by="creation desc"
	)

	users = [log.from_user for log in notification_logs]
	users = [*set(users)]  # remove duplicates
	user_info = frappe._dict()

	for user in users:
		frappe.utils.add_user_info(user, user_info)

	return {"notification_logs": notification_logs, "user_info": user_info}


@frappe.whitelist()
def mark_all_as_read():
	unread_docs_list = frappe.get_all(
		"Notification Log", filters={"read": 0, "for_user": frappe.session.user}
	)
	unread_docnames = [doc.name for doc in unread_docs_list]
	if unread_docnames:
		filters = {"name": ["in", unread_docnames]}
		frappe.db.set_value("Notification Log", filters, "read", 1, update_modified=False)


@frappe.whitelist()
def mark_as_read(docname: str):
	if frappe.flags.read_only:
		return

	if docname:
		frappe.db.set_value("Notification Log", str(docname), "read", 1, update_modified=False)


@frappe.whitelist()
def trigger_indicator_hide():
	frappe.publish_realtime("indicator_hide", user=frappe.session.user)


def set_notifications_as_unseen(user):
	try:
		frappe.db.set_value("Notification Settings", user, "seen", 0, update_modified=False)
	except frappe.DoesNotExistError:
		return
