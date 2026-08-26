# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Optional

import frappe

if TYPE_CHECKING:
	from frappe.email.doctype.email_queue.email_queue import EmailQueue


def sendmail_to_system_managers(subject, content):
	frappe.sendmail(recipients=get_system_managers(), subject=subject, content=content)


@frappe.whitelist()
def get_contact_list(txt: str, page_length: int = 20, extra_filters: str | None = None) -> list[dict]:
	"""Return email ids for a multiselect field."""
	if extra_filters:
		extra_filters = frappe.parse_json(extra_filters)

	filters = [
		["Contact Email", "email_id", "is", "set"],
	]
	if extra_filters:
		filters.extend(extra_filters)

	fields = ["first_name", "middle_name", "last_name", "company_name"]
	contacts = frappe.get_list(
		"Contact",
		fields=["full_name", "`tabContact Email`.email_id"],
		filters=filters,
		or_filters=[[field, "like", f"%{txt}%"] for field in fields]
		+ [["Contact Email", "email_id", "like", f"%{txt}%"]],
		limit_page_length=page_length,
	)

	# The multiselect field will store the `label` as the selected value.
	# The `value` is just used as a unique key to distinguish between the options.
	# https://github.com/frappe/frappe/blob/6c6a89bcdd9454060a1333e23b855d0505c9ebc2/frappe/public/js/frappe/form/controls/autocomplete.js#L29-L35
	return [
		frappe._dict(
			value=d.email_id,
			label=d.email_id,
			description=d.full_name,
		)
		for d in contacts
	]


@frappe.whitelist()
def get_recipient_avatars(emails: str) -> dict[str, str]:
	"""Map recipient email -> avatar image, for the email composer's recipient chips.

	Prefers the matching Contact's own `image`, falling back to the User with that
	email. Addresses with neither are absent from the result, so the caller can
	fall back to initials.
	"""
	emails = [e.strip().lower() for e in (frappe.parse_json(emails) or []) if e and e.strip()]
	if not emails:
		return {}

	Contact = frappe.qb.DocType("Contact")
	ContactEmail = frappe.qb.DocType("Contact Email")
	User = frappe.qb.DocType("User")

	# Contact.image, joined straight through the Contact Email child table
	contact_avatars = (
		frappe.qb.from_(ContactEmail)
		.select(ContactEmail.email_id, Contact.image)
		.inner_join(Contact)
		.on(Contact.name == ContactEmail.parent)
		.where(ContactEmail.email_id.isin(emails))
		.where(Contact.image.notnull())
		.where(Contact.image != "")
		.run()
	)

	# User.user_image. A User's id is usually the address but not always, so match
	# on either column — and key the result by whichever one the caller asked for.
	user_avatars = (
		frappe.qb.from_(User)
		.select(User.name, User.email, User.user_image)
		.where(User.name.isin(emails) | User.email.isin(emails))
		.where(User.user_image.notnull())
		.where(User.user_image != "")
		.run()
	)

	# users first, then contacts overwrite them — Contact wins where both exist
	avatars = {}
	for name, email, image in user_avatars:
		for key in (name, email):
			if key and key.lower() in emails:
				avatars[key.lower()] = image
	avatars.update({email.lower(): image for email, image in contact_avatars if email})
	return avatars


def get_system_managers():
	return frappe.db.sql_list(
		"""select parent FROM `tabHas Role`
		WHERE role='System Manager'
		AND parent!='Administrator'
		AND parent IN (SELECT email FROM tabUser WHERE enabled=1)"""
	)


@frappe.whitelist()
def relink(name: str, reference_doctype: str | None = None, reference_name: str | None = None):
	from frappe.core.doctype.comment.comment import relink_comment_cache

	frappe.has_permission("Communication", "write", name, throw=True)

	comm = frappe.get_doc("Communication", name)
	if comm.communication_type != "Communication":
		return

	old_reference_doctype = comm.reference_doctype
	old_reference_name = comm.reference_name

	frappe.db.sql(
		"""update
			`tabCommunication`
		set
			reference_doctype = %s,
			reference_name = %s,
			status = "Linked"
		where
			name = %s""",
		(reference_doctype, reference_name, name),
	)

	comm.reference_doctype = reference_doctype
	comm.reference_name = reference_name
	relink_comment_cache(comm, old_reference_doctype, old_reference_name)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_communication_doctype(
	doctype: str, txt: str, searchfield: str, start: int, page_len: int, filters: str | list | dict
):
	can_read = frappe.get_user().get_can_read()

	com_doctypes = frappe.db.get_values(
		"DocType", {"issingle": 0, "istable": 0, "hide_toolbar": 0}, pluck="name"
	)

	results = [[dt] for dt in list(set(com_doctypes)) if dt in can_read]

	return results


def sendmail(
	recipients=None,
	sender="",
	subject="No Subject",
	message="No Message",
	as_markdown=False,
	delayed=True,
	reference_doctype=None,
	reference_name=None,
	unsubscribe_method=None,
	unsubscribe_params=None,
	unsubscribe_message=None,
	add_unsubscribe_link=1,
	attachments=None,
	content=None,
	doctype=None,
	name=None,
	reply_to=None,
	queue_separately=False,
	cc=None,
	bcc=None,
	message_id=None,
	in_reply_to=None,
	send_after=None,
	expose_recipients=None,
	send_priority=1,
	communication=None,
	retry=1,
	now=None,
	read_receipt=None,
	is_notification=False,
	inline_images=None,
	template=None,
	args=None,
	header=None,
	print_letterhead=False,
	with_container=False,
	email_read_tracker_url=None,
	x_priority: Literal[1, 3, 5] = 3,
	email_headers=None,
	raw_html=False,
	add_css=True,
	redact_message_after_send=False,
) -> EmailQueue | None:
	"""Send email using user's default **Email Account** or global default **Email Account**.


	    :param recipients: List of recipients.
	    :param sender: Email sender. Default is current user or default outgoing account.
	    :param subject: Email Subject.
	    :param message: (or `content`) Email Content.
	    :param as_markdown: Convert content markdown to HTML.
	    :param delayed: Send via scheduled email sender **Email Queue**. Don't send immediately. Default is true
	    :param send_priority: Priority for Email Queue, default 1.
	    :param reference_doctype: (or `doctype`) Append as communication to this DocType.
	    :param reference_name: (or `name`) Append as communication to this document name.
	    :param unsubscribe_method: Unsubscribe url with options email, doctype, name. e.g. `/api/method/unsubscribe`
	    :param unsubscribe_params: Unsubscribe paramaters to be loaded on the unsubscribe_method [optional] (dict).
	    :param attachments: List of attachments.
	    :param reply_to: Reply-To Email Address.
	    :param message_id: Used for threading. If a reply is received to this email, Message-Id is sent back as In-Reply-To in received email.
	    :param in_reply_to: Used to send the Message-Id of a received email back as In-Reply-To.
	    :param send_after: Send after the given datetime.
	    :param expose_recipients: Controls recipient visibility. "header" shows all TO recipients in the To header.
	"footer" adds "This email was sent to..." text in footer. None (default) hides TO recipients from each other.
	Note: CC header is always visible regardless of this setting (as per email semantics).
	    :param communication: Communication link to be set in Email Queue record
	    :param inline_images: List of inline images as {"filename", "filecontent"}. All src properties will be replaced with random Content-Id
	    :param template: Name of html template from templates/emails folder
	    :param args: Arguments for rendering the template
	    :param header: Append header in email
	    :param with_container: Wraps email inside a styled container
	    :param x_priority: 1 = HIGHEST, 3 = NORMAL, 5 = LOWEST
	    :param email_headers: Additional headers to be added in the email, e.g. {"X-Custom-Header": "value"} or {"Custom-Header": "value"}. Automatically prepends "X-" to the header name if not present.
	    :param raw_html: Whether to treat email template as a complete HTML file
	    :param add_css: Whether to add CSS from hooks/email_css to the email template
	    :param redact_message_after_send: Replace the message body with a placeholder once sent, for emails carrying sensitive content.
	"""

	from frappe.utils.jinja import get_email_from_template

	if recipients is None:
		recipients = []
	if cc is None:
		cc = []
	if bcc is None:
		bcc = []

	text_content = None
	if template:
		message, text_content = get_email_from_template(template, args)

	message = content or message

	if as_markdown:
		from frappe.utils import md_to_html

		message = md_to_html(message)

	if not delayed:
		now = True

	from frappe.email.doctype.email_queue.email_queue import QueueBuilder

	builder = QueueBuilder(
		recipients=recipients,
		sender=sender,
		subject=subject,
		message=message,
		text_content=text_content,
		reference_doctype=doctype or reference_doctype,
		reference_name=name or reference_name,
		add_unsubscribe_link=add_unsubscribe_link,
		unsubscribe_method=unsubscribe_method,
		unsubscribe_params=unsubscribe_params,
		unsubscribe_message=unsubscribe_message,
		attachments=attachments,
		reply_to=reply_to,
		cc=cc,
		bcc=bcc,
		message_id=message_id,
		in_reply_to=in_reply_to,
		send_after=send_after,
		expose_recipients=expose_recipients,
		send_priority=send_priority,
		queue_separately=queue_separately,
		communication=communication,
		read_receipt=read_receipt,
		is_notification=is_notification,
		inline_images=inline_images,
		header=header,
		print_letterhead=print_letterhead,
		with_container=with_container,
		email_read_tracker_url=email_read_tracker_url,
		x_priority=x_priority,
		email_headers=email_headers,
		raw_html=raw_html,
		add_css=add_css,
		redact_message_after_send=redact_message_after_send,
	)

	# build email queue and send the email if send_now is True.

	q = builder.process(send_now=False)
	if now and q:
		frappe.db.after_commit.add(q.send)
	return q
