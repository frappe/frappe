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
from frappe.utils import get_url, nowdate, encode, now_datetime, add_days, split_emails, cstr, cint
from rq.timeouts import JobTimeoutException
from frappe.utils.scheduler import log

class EmailLimitCrossedError(frappe.ValidationError): pass

def send(recipients=None, sender=None, subject=None, message=None, reference_doctype=None,
		reference_name=None, unsubscribe_method=None, unsubscribe_params=None, unsubscribe_message=None,
		attachments=None, reply_to=None, cc=(), show_as_cc=(), message_id=None, in_reply_to=None, send_after=None,
		expose_recipients=False, send_priority=1, communication=None, read_receipt=None):
	"""Add email to sending queue (Email Queue)

	:param recipients: List of recipients.
	:param sender: Email sender.
	:param subject: Email subject.
	:param message: Email message.
	:param reference_doctype: Reference DocType of caller document.
	:param reference_name: Reference name of caller document.
	:param send_priority: Priority for Email Queue, default 1.
	:param unsubscribe_method: URL method for unsubscribe. Default is `/api/method/frappe.email.queue.unsubscribe`.
	:param unsubscribe_params: additional params for unsubscribed links. default are name, doctype, email
	:param attachments: Attachments to be sent.
	:param reply_to: Reply to be captured here (default inbox)
	:param message_id: Used for threading. If a reply is received to this email, Message-Id is sent back as In-Reply-To in received email.
	:param in_reply_to: Used to send the Message-Id of a received email back as In-Reply-To.
	:param send_after: Send this email after the given datetime. If value is in integer, then `send_after` will be the automatically set to no of days from current date.
	:param communication: Communication link to be set in Email Queue record
	"""
	if not unsubscribe_method:
		unsubscribe_method = "/api/method/frappe.email.queue.unsubscribe"

	if not recipients:
		return

	if isinstance(recipients, basestring):
		recipients = split_emails(recipients)

	if isinstance(send_after, int):
		send_after = add_days(nowdate(), send_after)

	email_account = get_outgoing_email_account(True, append_to=reference_doctype)
	if not sender or sender == "Administrator":
		sender = email_account.default_sender

	check_email_limit(recipients)

	formatted = get_formatted_html(subject, message, email_account=email_account)

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
			reference_name, attachments, reply_to, cc, message_id, in_reply_to, send_after, send_priority, email_account=email_account, communication=communication, read_receipt=read_receipt)

def add(email, sender, subject, formatted, text_content=None,
	reference_doctype=None, reference_name=None, attachments=None, reply_to=None,
	cc=(), message_id=None, in_reply_to=None, send_after=None, send_priority=1, email_account=None, communication=None):
	"""Add to Email Queue"""
	e = frappe.new_doc('Email Queue')
	e.recipient = email
	e.priority = send_priority

	try:
		mail = get_email(email, sender=sender, formatted=formatted, subject=subject,
			text_content=text_content, attachments=attachments, reply_to=reply_to, cc=cc, email_account=email_account)

		mail.set_message_id(message_id)
		if read_receipt:
			mail.msg_root["Disposition-Notification-To"] = sender
		if in_reply_to:
			mail.set_in_reply_to(in_reply_to)

		e.message = cstr(mail.as_string())
		e.sender = mail.sender

	except frappe.InvalidEmailAddressError:
		# bad email id - don't add to queue
		return

	e.reference_doctype = reference_doctype
	e.reference_name = reference_name
	e.communication = communication
	e.send_after = send_after
	e.db_insert()

def check_email_limit(recipients):
	# if using settings from site_config.json, check email limit
	# No limit for own email settings
	smtp_server = SMTPServer()

	if (smtp_server.email_account
		and getattr(smtp_server.email_account, "from_site_config", False)
		or frappe.flags.in_test):

		# get count of mails sent this month
		this_month = get_emails_sent_this_month()

		monthly_email_limit = frappe.conf.get('limits', {}).get('emails') or 500

		if frappe.flags.in_test:
			monthly_email_limit = 500

		if (this_month + len(recipients)) > monthly_email_limit:
			throw(_("Cannot send this email. You have crossed the sending limit of {0} emails for this month.").format(monthly_email_limit),
				EmailLimitCrossedError)

def get_emails_sent_this_month():
	return frappe.db.sql("""select count(name) from `tabEmail Queue` where
		status='Sent' and MONTH(creation)=MONTH(CURDATE())""")[0][0]

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
	# additional check
	cache = frappe.cache()
	check_email_limit([])

	auto_commit = not from_test
	if frappe.are_emails_muted():
		msgprint(_("Emails are muted"))
		from_test = True

	smtpserver = SMTPServer()

	make_cache_queue()

	for i in xrange(cache.llen('cache_email_queue')):
		email = cache.lpop('cache_email_queue')

		if cint(frappe.defaults.get_defaults().get("hold_bulk"))==1:
			break
		
		if email:
			send_one(email, smtpserver, auto_commit)

		# NOTE: removing commit here because we pass auto_commit
		# finally:
		# 	frappe.db.commit()
def make_cache_queue():
	'''cache values in queue before sendign'''
	cache = frappe.cache()

	emails = frappe.db.sql('''select name from `tabEmail Queue`
		where status='Not Sent' and (send_after is null or send_after < %(now)s)
		order by priority desc, creation asc
		limit 500''', { 'now': now_datetime() })

	# reset value
	cache.delete_value('cache_email_queue')
	for e in emails:
		cache.rpush('cache_email_queue', e[0])

def send_one(email, smtpserver=None, auto_commit=True, now=False):
	'''Send Email Queue with given smtpserver'''

	email = frappe.db.sql('''select name, status, communication,
		message, sender, recipient, reference_doctype
		from `tabEmail Queue` where name=%s for update''', email, as_dict=True)[0]
	if email.status != 'Not Sent':
		# rollback to release lock and return
		frappe.db.rollback()
		return

	frappe.db.sql("""update `tabEmail Queue` set status='Sending', modified=%s where name=%s""",
		(now_datetime(), email.name), auto_commit=auto_commit)

	if email.communication:
		frappe.get_doc('Communication', email.communication).set_delivery_status(commit=auto_commit)

	try:
		if auto_commit:
			if not smtpserver: smtpserver = SMTPServer()
			smtpserver.setup_email_account(email.reference_doctype)
			smtpserver.sess.sendmail(email.sender, email.recipient, encode(email.message))

		frappe.db.sql("""update `tabEmail Queue` set status='Sent', modified=%s where name=%s""",
			(now_datetime(), email.name), auto_commit=auto_commit)

		if email.communication:
			frappe.get_doc('Communication', email.communication).set_delivery_status(commit=auto_commit)

	except (smtplib.SMTPServerDisconnected,
			smtplib.SMTPConnectError,
			smtplib.SMTPHeloError,
			smtplib.SMTPAuthenticationError,
			frappe.ValidationError):

		# bad connection/timeout, retry later
		frappe.db.sql("""update `tabEmail Queue` set status='Not Sent', modified=%s where name=%s""",
			(now_datetime(), email.name), auto_commit=auto_commit)

		if email.communication:
			frappe.get_doc('Communication', email.communication).set_delivery_status(commit=auto_commit)

		# no need to attempt further
		return

	except Exception, e:
		frappe.db.rollback()

		frappe.db.sql("""update `tabEmail Queue` set status='Error', error=%s
			where name=%s""", (unicode(e), email.name), auto_commit=auto_commit)

		if email.communication:
			frappe.get_doc('Communication', email.communication).set_delivery_status(commit=auto_commit)

		if now:
			raise e

		else:
			# log to Error Log
			log('frappe.email.queue.flush', unicode(e))

def clear_outbox():
	"""Remove mails older than 31 days in Outbox. Called daily via scheduler."""
	frappe.db.sql("""delete from `tabEmail Queue` where
		datediff(now(), creation) > 31""")

	frappe.db.sql("""update `tabEmail Queue` set status='Expired'
		where datediff(curdate(), creation) > 7 and status='Not Sent'""")
