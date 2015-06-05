# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import HTMLParser
from frappe import msgprint, throw, _
from frappe.email.smtp import SMTPServer, get_outgoing_email_account
from frappe.email.email_body import get_email, get_formatted_html
from frappe.utils.verified_command import get_signed_params, verify_request
from html2text import html2text
from frappe.utils import get_url, nowdate, encode, now_datetime, add_days

class BulkLimitCrossedError(frappe.ValidationError): pass

def send(recipients=None, sender=None, subject=None, message=None, reference_doctype=None,
		reference_name=None, unsubscribe_method=None, unsubscribe_params=None, unsubscribe_message=None,
		attachments=None, reply_to=None, cc=(), message_id=None, send_after=None):
	"""Add email to sending queue (Bulk Email)

	:param recipients: List of recipients.
	:param sender: Email sender.
	:param subject: Email subject.
	:param message: Email message.
	:param reference_doctype: Reference DocType of caller document.
	:param reference_name: Reference name of caller document.
	:param unsubscribe_method: URL method for unsubscribe. Default is `/api/method/frappe.email.bulk.unsubscribe`.
	:param unsubscribe_params: additional params for unsubscribed links. default are name, doctype, email
	:param attachments: Attachments to be sent.
	:param reply_to: Reply to be captured here (default inbox)
	:param message_id: Used for threading. If a reply is received to this email, Message-Id is sent back as In-Reply-To in received email.
	:param send_after: Send this email after the given datetime. If value is in integer, then `send_after` will be the automatically set to no of days from current date.
	"""
	if not unsubscribe_method:
		unsubscribe_method = "/api/method/frappe.email.bulk.unsubscribe"

	if not recipients:
		return

	if isinstance(recipients, basestring):
		recipients = recipients.split(",")

	if isinstance(send_after, int):
		send_after = add_days(nowdate(), send_after)

	if not sender or sender == "Administrator":
		email_account = get_outgoing_email_account()
		sender = email_account.get("sender") or email_account.email_id

	check_bulk_limit(recipients)

	formatted = get_formatted_html(subject, message)

	try:
		text_content = html2text(formatted)
	except HTMLParser.HTMLParseError:
		text_content = "See html attachment"

	if reference_doctype and reference_name:
		unsubscribed = [d.email for d in frappe.db.get_all("Email Unsubscribe", "email",
			{"reference_doctype": reference_doctype, "reference_name": reference_name})]
	else:
		unsubscribed = []

	for email in filter(None, list(set(recipients))):
		if email not in unsubscribed:
			email_content = formatted
			email_text_context = text_content

			if reference_doctype:
				unsubscribe_url = get_unsubcribed_url(reference_doctype, reference_name, email,
					unsubscribe_method, unsubscribe_params)

				# add to queue
				email_content = add_unsubscribe_link(email_content, email, reference_doctype,
					reference_name, unsubscribe_url, unsubscribe_message)

				email_text_context += "\n" + _("This email was sent to {0}. To unsubscribe click on this link: {1}").format(email, unsubscribe_url)

			add(email, sender, subject, email_content, email_text_context, reference_doctype,
				reference_name, attachments, reply_to, cc, message_id, send_after)

def add(email, sender, subject, formatted, text_content=None,
	reference_doctype=None, reference_name=None, attachments=None, reply_to=None,
	cc=(), message_id=None, send_after=None):
	"""add to bulk mail queue"""
	e = frappe.new_doc('Bulk Email')
	e.sender = sender
	e.recipient = email

	try:
		mail = get_email(email, sender=e.sender, formatted=formatted, subject=subject,
			text_content=text_content, attachments=attachments, reply_to=reply_to, cc=cc)

		if message_id:
			mail.set_message_id(message_id)

		e.message = mail.as_string()

	except frappe.InvalidEmailAddressError:
		# bad email id - don't add to queue
		return

	e.reference_doctype = reference_doctype
	e.reference_name = reference_name
	e.send_after = send_after
	e.insert(ignore_permissions=True)

def check_bulk_limit(recipients):
	this_month = frappe.db.sql("""select count(*) from `tabBulk Email` where
		MONTH(creation)=MONTH(CURDATE())""")[0][0]

	# No limit for own email settings
	smtp_server = SMTPServer()

	if smtp_server.email_account and getattr(smtp_server.email_account,
		"from_site_config", False) or frappe.flags.in_test:
		monthly_bulk_mail_limit = frappe.conf.get('monthly_bulk_mail_limit') or 500

		if (this_month + len(recipients)) > monthly_bulk_mail_limit:
			throw(_("Email limit {0} crossed").format(monthly_bulk_mail_limit),
				BulkLimitCrossedError)

def add_unsubscribe_link(message, email, reference_doctype, reference_name, unsubscribe_url, unsubscribe_message):
	unsubscribe_link = """<div style="padding: 7px; text-align: center; color: #8D99A6;">
			{email}. <a href="{unsubscribe_url}" style="color: #8D99A6; text-decoration: underline;
				target="_blank">{unsubscribe_message}.
			</a>
		</div>""".format(unsubscribe_url = unsubscribe_url,
			email= _("This email was sent to {0}").format(email),
			unsubscribe_message = unsubscribe_message or _("Unsubscribe from this list"))

	message = message.replace("<!--unsubscribe link here-->", unsubscribe_link)

	return message

def get_unsubcribed_url(reference_doctype, reference_name, email, unsubscribe_method, unsubscribe_params):
	params = {"email": email.encode("utf-8"),
		"doctype": reference_doctype.encode("utf-8"),
		"name": reference_name.encode("utf-8")}
	if unsubscribe_params:
		params.update(unsubscribe_params)

	query_string = get_signed_params(params)

	# for test
	frappe.local.flags.signed_query_string = query_string

	return get_url(unsubscribe_method + "?" + get_signed_params(params))

@frappe.whitelist(allow_guest=True)
def unsubscribe(doctype, name, email):
	# unsubsribe from comments and communications
	if not verify_request():
		return

	frappe.get_doc({
		"doctype": "Email Unsubscribe",
		"email": email,
		"reference_doctype": doctype,
		"reference_name": name
	}).insert(ignore_permissions=True)

	frappe.db.commit()

	return_unsubscribed_page(email, doctype, name)

def return_unsubscribed_page(email, doctype, name):
	frappe.respond_as_web_page(_("Unsubscribed"), _("{0} has left the conversation in {1} {2}").format(email, _(doctype), name))

def flush(from_test=False):
	"""flush email queue, every time: called from scheduler"""
	smtpserver = SMTPServer()

	auto_commit = not from_test

	if frappe.flags.mute_emails or frappe.conf.get("mute_emails") or False:
		msgprint(_("Emails are muted"))
		from_test = True

	frappe.db.sql("""update `tabBulk Email` set status='Expired'
		where datediff(curdate(), creation) > 3""", auto_commit=auto_commit)

	for i in xrange(500):
		email = frappe.db.sql("""select * from `tabBulk Email` where
			status='Not Sent' and ifnull(send_after, "2000-01-01 00:00:00") < %s
			order by creation asc limit 1 for update""", now_datetime(), as_dict=1)
		if email:
			email = email[0]
		else:
			break

		frappe.db.sql("""update `tabBulk Email` set status='Sending' where name=%s""",
			(email["name"],), auto_commit=auto_commit)
		try:
			if not from_test:
				smtpserver.setup_email_account(email.reference_doctype)
				smtpserver.sess.sendmail(email["sender"], email["recipient"], encode(email["message"]))

			frappe.db.sql("""update `tabBulk Email` set status='Sent' where name=%s""",
				(email["name"],), auto_commit=auto_commit)

		except Exception, e:
			frappe.db.sql("""update `tabBulk Email` set status='Error', error=%s
				where name=%s""", (unicode(e), email["name"]), auto_commit=auto_commit)

def clear_outbox():
	"""remove mails older than 30 days in Outbox"""
	frappe.db.sql("""delete from `tabBulk Email` where
		datediff(now(), creation) > 30""")
