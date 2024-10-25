# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe import _, msgprint
from frappe.utils import cint, cstr, get_url, now_datetime
from frappe.utils.data import getdate
from frappe.utils.verified_command import get_signed_params, verify_request

# After this percent of failures in every batch, entire batch is aborted.
# This usually indicates a systemic failure so we shouldn't keep trying to send emails.
EMAIL_QUEUE_BATCH_FAILURE_THRESHOLD_PERCENT = 0.33
EMAIL_QUEUE_BATCH_FAILURE_THRESHOLD_COUNT = 10


def get_emails_sent_this_month(email_account=None):
	"""Get count of emails sent from a specific email account.

	:param email_account: name of the email account used to send mail

	if email_account=None, email account filter is not applied while counting
	"""
	today = getdate()
	month_start = today.replace(day=1)

	filters = {
		"status": "Sent",
		"creation": [">=", str(month_start)],
	}
	if email_account:
		filters["email_account"] = email_account

	return frappe.db.count("Email Queue", filters=filters)


def get_emails_sent_today(email_account=None):
	"""Get count of emails sent from a specific email account.

	:param email_account: name of the email account used to send mail

	if email_account=None, email account filter is not applied while counting
	"""
	q = """
		SELECT
			COUNT(`name`)
		FROM
			`tabEmail Queue`
		WHERE
			`status` in ('Sent', 'Not Sent', 'Sending')
			AND
			`creation` > (NOW() - INTERVAL '24' HOUR)
	"""

	q_args = {}
	if email_account is not None:
		if email_account:
			q += " AND email_account = %(email_account)s"
			q_args["email_account"] = email_account
		else:
			q += " AND (email_account is null OR email_account='')"

	return frappe.db.sql(q, q_args)[0][0]


def get_unsubscribe_message(unsubscribe_message: str, expose_recipients: str) -> "frappe._dict[str, str]":
	unsubscribe_message = unsubscribe_message or _("Unsubscribe")
	unsubscribe_link = f'<a href="<!--unsubscribe_url-->" target="_blank">{unsubscribe_message}</a>'
	unsubscribe_html = _("{0} to stop receiving emails of this type").format(unsubscribe_link)
	html = f"""<div class="email-unsubscribe">
			<!--cc_message-->
			<div>
				{unsubscribe_html}
			</div>
		</div>"""

	text = f"\n\n{unsubscribe_message}: <!--unsubscribe_url-->\n"
	if expose_recipients == "footer":
		text = f"\n<!--cc_message-->{text}"

	return frappe._dict(html=html, text=text)


def get_unsubcribed_url(reference_doctype, reference_name, email, unsubscribe_method, unsubscribe_params):
	params = {
		"email": cstr(email),
		"doctype": cstr(reference_doctype),
		"name": cstr(reference_name),
	}
	if unsubscribe_params:
		params.update(unsubscribe_params)

	return get_url(unsubscribe_method + "?" + get_signed_params(params))


@frappe.whitelist(allow_guest=True)
def unsubscribe(doctype, name, email) -> None:
	# unsubsribe from comments and communications
	if not frappe.flags.in_test and not verify_request():
		return

	try:
		frappe.get_doc(
			{
				"doctype": "Email Unsubscribe",
				"email": email,
				"reference_doctype": doctype,
				"reference_name": name,
			}
		).insert(ignore_permissions=True)

	except frappe.DuplicateEntryError:
		frappe.db.rollback()

	else:
		frappe.db.commit()

	return_unsubscribed_page(email, doctype, name)


def return_unsubscribed_page(email, doctype, name) -> None:
	frappe.respond_as_web_page(
		_("Unsubscribed"),
		_("{0} has left the conversation in {1} {2}").format(email, _(doctype), name),
		indicator_color="green",
	)


def flush() -> None:
	"""flush email queue, every time: called from scheduler.

	This should not be called outside of background jobs.
	"""
	from frappe.email.doctype.email_queue.email_queue import EmailQueue

	# To avoid running jobs inside unit tests
	if frappe.are_emails_muted():
		msgprint(_("Emails are muted"))

	if cint(frappe.db.get_default("suspend_email_queue")) == 1:
		return

	email_queue_batch = get_queue()
	if not email_queue_batch:
		return

	failed_email_queues = []
	for row in email_queue_batch:
		try:
			email_queue: EmailQueue = frappe.get_doc("Email Queue", row.name)
			email_queue.send()
		except Exception:
			frappe.get_doc("Email Queue", row.name).log_error()
			failed_email_queues.append(row.name)

			if (
				len(failed_email_queues) / len(email_queue_batch)
				> EMAIL_QUEUE_BATCH_FAILURE_THRESHOLD_PERCENT
				and len(failed_email_queues) > EMAIL_QUEUE_BATCH_FAILURE_THRESHOLD_COUNT
			):
				frappe.throw(_("Email Queue flushing aborted due to too many failures."))


def get_queue():
	batch_size = cint(frappe.conf.email_queue_batch_size) or 500

	return frappe.db.sql(
		f"""select
			name, sender
		from
			`tabEmail Queue`
		where
			(status='Not Sent' or status='Partially Sent') and
			(send_after is null or send_after < %(now)s)
		order
			by priority desc, retry asc, creation asc
		limit {batch_size}""",
		{"now": now_datetime()},
		as_dict=True,
	)
