# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import HTMLParser
import smtplib
from frappe import msgprint, throw, _
from frappe.email.smtp import SMTPServer, get_outgoing_email_account
from frappe.email.email_body import get_email, get_formatted_html
from frappe.utils.verified_command import get_signed_params, verify_request
from html2text import html2text
from frappe.utils import get_url, nowdate, encode, now_datetime, add_days, split_emails

class BulkLimitCrossedError(frappe.ValidationError): pass

def send(recipients=None, sender=None, subject=None, message=None, reference_doctype=None,
		reference_name=None, unsubscribe_method=None, unsubscribe_params=None, unsubscribe_message=None,
		attachments=None, reply_to=None, cc=(), show_as_cc=(), message_id=None, send_after=None,
		expose_recipients=False, bulk_priority=1):
	"""Add email to sending queue (Bulk Email)

	:param recipients: List of recipients.
	:param sender: Email sender.
	:param subject: Email subject.
	:param message: Email message.
	:param reference_doctype: Reference DocType of caller document.
	:param reference_name: Reference name of caller document.
	:param bulk_priority: Priority for bulk email, default 1.
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
		recipients = split_emails(recipients)

	if isinstance(send_after, int):
		send_after = add_days(nowdate(), send_after)

	if not sender or sender == "Administrator":
		email_account = get_outgoing_email_account()
		sender = email_account.default_sender

	check_bulk_limit(recipients)

	formatted = get_formatted_html(subject, message)

	try:
		text_content = html2text(formatted)
	except HTMLParser.HTMLParseError:
		text_content = "See html attachment"

	if reference_doctype and reference_name:
		unsubscribed = [d.email for d in frappe.db.get_all("Email Unsubscribe", "email",
			{"reference_doctype": reference_doctype, "reference_name": reference_name})]

		unsubscribed += [d.email for d in frappe.db.get_all("Email Unsubscribe", "email",
			{"global_unsubscribe": 1})]
	else:
		unsubscribed = []

	recipients = [r for r in list(set(recipients)) if r and r not in unsubscribed]

	for email in recipients:
		email_content = formatted
		email_text_context = text_content

		if reference_doctype:
			unsubscribe_link = get_unsubscribe_link(
				reference_doctype=reference_doctype,
				reference_name=reference_name,
				email=email,
				recipients=recipients,
				expose_recipients=expose_recipients,
				unsubscribe_method=unsubscribe_method,
				unsubscribe_params=unsubscribe_params,
				unsubscribe_message=unsubscribe_message,
				show_as_cc=show_as_cc
			)

			email_content = email_content.replace("<!--unsubscribe link here-->", unsubscribe_link.html)
			email_text_context += unsubscribe_link.text

			# show as cc
			cc_message = ""
			if email in show_as_cc:
				cc_message = _("This email was sent to you as CC")

			email_content = email_content.replace("<!-- cc message -->", cc_message)
			email_text_context = cc_message + "\n" + email_text_context

		# add to queue
		add(email, sender, subject, email_content, email_text_context, reference_doctype,
			reference_name, attachments, reply_to, cc, message_id, send_after, bulk_priority)

def add(email, sender, subject, formatted, text_content=None,
	reference_doctype=None, reference_name=None, attachments=None, reply_to=None,
	cc=(), message_id=None, send_after=None, bulk_priority=1):
	"""add to bulk mail queue"""
	e = frappe.new_doc('Bulk Email')
	e.sender = sender
	e.recipient = email
	e.priority = bulk_priority

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
	# get count of mails sent this month
	this_month = frappe.db.sql("""select count(*) from `tabBulk Email` where
		status='Sent' and MONTH(creation)=MONTH(CURDATE())""")[0][0]

	# if using settings from site_config.json, check bulk limit
	# No limit for own email settings
	smtp_server = SMTPServer()

	if (smtp_server.email_account
		and getattr(smtp_server.email_account, "from_site_config", False)
		or frappe.flags.in_test):

		monthly_bulk_mail_limit = frappe.conf.get('monthly_bulk_mail_limit') or 500

		if (this_month + len(recipients)) > monthly_bulk_mail_limit:
			throw(_("Cannot send this email. You have crossed the sending limit of {0} emails for this month.").format(monthly_bulk_mail_limit),
				BulkLimitCrossedError)

def get_unsubscribe_link(reference_doctype, reference_name,
	email, recipients, expose_recipients, show_as_cc,
	unsubscribe_method, unsubscribe_params, unsubscribe_message):

	email_sent_to = recipients if expose_recipients else [email]
	email_sent_cc = ", ".join([e for e in email_sent_to if e in show_as_cc])
	email_sent_to = ", ".join([e for e in email_sent_to if e not in show_as_cc])

	if email_sent_cc:
		email_sent_message = _("This email was sent to {0} and copied to {1}").format(email_sent_to, email_sent_cc)
	else:
		email_sent_message = _("This email was sent to {0}").format(email_sent_to)

	if not unsubscribe_message:
		unsubscribe_message = _("Unsubscribe from this list")

	unsubscribe_url = get_unsubcribed_url(reference_doctype, reference_name, email,
		unsubscribe_method, unsubscribe_params)

	html = """<div style="margin: 15px auto; padding: 0px 7px; text-align: center; color: #8d99a6;">
			{email}
			<p style="margin: 15px auto;">
				<a href="{unsubscribe_url}" style="color: #8d99a6; text-decoration: underline;
					target="_blank">{unsubscribe_message}
				</a>
			</p>
		</div>""".format(
			unsubscribe_url = unsubscribe_url,
			email=email_sent_message,
			unsubscribe_message=unsubscribe_message
		)

	text = "\n{email}\n\n{unsubscribe_message}: {unsubscribe_url}".format(
		email=email_sent_message,
		unsubscribe_message=unsubscribe_message,
		unsubscribe_url=unsubscribe_url
	)

	return frappe._dict({
		"html": html,
		"text": text
	})

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

	try:
		frappe.get_doc({
			"doctype": "Email Unsubscribe",
			"email": email,
			"reference_doctype": doctype,
			"reference_name": name
		}).insert(ignore_permissions=True)

	except frappe.DuplicateEntryError:
		frappe.db.rollback()

	else:
		frappe.db.commit()

	return_unsubscribed_page(email, doctype, name)

def return_unsubscribed_page(email, doctype, name):
	frappe.respond_as_web_page(_("Unsubscribed"), _("{0} has left the conversation in {1} {2}").format(email, _(doctype), name))

def flush(from_test=False):
	"""flush email queue, every time: called from scheduler"""
	smtpserver = SMTPServer()

	auto_commit = not from_test

	# additional check
	check_bulk_limit([])

	if frappe.are_emails_muted():
		msgprint(_("Emails are muted"))
		from_test = True

	frappe.db.sql("""update `tabBulk Email` set status='Expired'
		where datediff(curdate(), creation) > 3""", auto_commit=auto_commit)

	for i in xrange(500):
		email = frappe.db.sql("""select * from `tabBulk Email` where
			status='Not Sent' and ifnull(send_after, "2000-01-01 00:00:00") < %s
			order by priority desc, creation asc limit 1 for update""", now_datetime(), as_dict=1)
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

		except (smtplib.SMTPServerDisconnected,
				smtplib.SMTPConnectError,
				smtplib.SMTPHeloError,
				smtplib.SMTPAuthenticationError):

			# bad connection, retry later
			frappe.db.sql("""update `tabBulk Email` set status='Not Sent' where name=%s""",
				(email["name"],), auto_commit=auto_commit)

			# no need to attempt further
			return

		except Exception, e:
			frappe.db.sql("""update `tabBulk Email` set status='Error', error=%s
				where name=%s""", (unicode(e), email["name"]), auto_commit=auto_commit)

		finally:
			frappe.db.commit()

def clear_outbox():
	"""Remove mails older than 31 days in Outbox. Called daily via scheduler."""
	frappe.db.sql("""delete from `tabBulk Email` where
		datediff(now(), creation) > 31""")
