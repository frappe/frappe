# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
from six.moves import range
import frappe
from six.moves import html_parser as HTMLParser
import smtplib, quopri, json
from frappe import msgprint, throw, _
from frappe.email.smtp import SMTPServer, get_outgoing_email_account
from frappe.email.email_body import get_email, get_formatted_html, add_attachment
from frappe.utils.verified_command import get_signed_params, verify_request
from html2text import html2text
from frappe.utils import get_url, nowdate, encode, now_datetime, add_days, split_emails, cstr, cint
from frappe.utils.file_manager import get_file
from rq.timeouts import JobTimeoutException
from frappe.utils.scheduler import log
from six import text_type, string_types

class EmailLimitCrossedError(frappe.ValidationError): pass

def send(recipients=None, sender=None, subject=None, message=None, text_content=None, reference_doctype=None,
		reference_name=None, unsubscribe_method=None, unsubscribe_params=None, unsubscribe_message=None,
		attachments=None, reply_to=None, cc=[], message_id=None, in_reply_to=None, send_after=None,
		expose_recipients=None, send_priority=1, communication=None, now=False, read_receipt=None,
		queue_separately=False, is_notification=False, add_unsubscribe_link=1, inline_images=None,
		header=None):
	"""Add email to sending queue (Email Queue)

	:param recipients: List of recipients.
	:param sender: Email sender.
	:param subject: Email subject.
	:param message: Email message.
	:param text_content: Text version of email message.
	:param reference_doctype: Reference DocType of caller document.
	:param reference_name: Reference name of caller document.
	:param send_priority: Priority for Email Queue, default 1.
	:param unsubscribe_method: URL method for unsubscribe. Default is `/api/method/frappe.email.queue.unsubscribe`.
	:param unsubscribe_params: additional params for unsubscribed links. default are name, doctype, email
	:param attachments: Attachments to be sent.
	:param reply_to: Reply to be captured here (default inbox)
	:param in_reply_to: Used to send the Message-Id of a received email back as In-Reply-To.
	:param send_after: Send this email after the given datetime. If value is in integer, then `send_after` will be the automatically set to no of days from current date.
	:param communication: Communication link to be set in Email Queue record
	:param now: Send immediately (don't send in the background)
	:param queue_separately: Queue each email separately
	:param is_notification: Marks email as notification so will not trigger notifications from system
	:param add_unsubscribe_link: Send unsubscribe link in the footer of the Email, default 1.
	:param inline_images: List of inline images as {"filename", "filecontent"}. All src properties will be replaced with random Content-Id
	:param header: Append header in email (boolean)
	"""
	if not unsubscribe_method:
		unsubscribe_method = "/api/method/frappe.email.queue.unsubscribe"

	if not recipients and not cc:
		return

	if isinstance(recipients, string_types):
		recipients = split_emails(recipients)

	if isinstance(cc, string_types):
		cc = split_emails(cc)

	if isinstance(send_after, int):
		send_after = add_days(nowdate(), send_after)

	email_account = get_outgoing_email_account(True, append_to=reference_doctype, sender=sender)
	if not sender or sender == "Administrator":
		sender = email_account.default_sender

	check_email_limit(recipients)

	if not text_content:
		try:
			text_content = html2text(message)
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

	email_text_context = text_content

	should_append_unsubscribe = (add_unsubscribe_link
		and reference_doctype
		and (unsubscribe_message or reference_doctype=="Newsletter")
		and add_unsubscribe_link==1)

	unsubscribe_link = None
	if should_append_unsubscribe:
		unsubscribe_link = get_unsubscribe_message(unsubscribe_message, expose_recipients)
		email_text_context += unsubscribe_link.text

	email_content = get_formatted_html(subject, message,
		email_account=email_account, header=header,
		unsubscribe_link=unsubscribe_link)

	# add to queue
	add(recipients, sender, subject,
		formatted=email_content,
		text_content=email_text_context,
		reference_doctype=reference_doctype,
		reference_name=reference_name,
		attachments=attachments,
		reply_to=reply_to,
		cc=cc,
		message_id=message_id,
		in_reply_to=in_reply_to,
		send_after=send_after,
		send_priority=send_priority,
		email_account=email_account,
		communication=communication,
		add_unsubscribe_link=add_unsubscribe_link,
		unsubscribe_method=unsubscribe_method,
		unsubscribe_params=unsubscribe_params,
		expose_recipients=expose_recipients,
		read_receipt=read_receipt,
		queue_separately=queue_separately,
		is_notification = is_notification,
		inline_images = inline_images,
		header=header,
		now=now)


def add(recipients, sender, subject, **kwargs):
	"""Add to Email Queue"""
	if kwargs.get('queue_separately') or len(recipients) > 20:
		email_queue = None
		for r in recipients:
			if not email_queue:
				email_queue = get_email_queue([r], sender, subject, **kwargs)
				if kwargs.get('now'):
					email_queue(email_queue.name, now=True)
			else:
				duplicate = email_queue.get_duplicate([r])
				duplicate.insert(ignore_permissions=True)

				if kwargs.get('now'):
					send_one(duplicate.name, now=True)

			frappe.db.commit()
	else:
		email_queue = get_email_queue(recipients, sender, subject, **kwargs)
		if kwargs.get('now'):
			send_one(email_queue.name, now=True)

def get_email_queue(recipients, sender, subject, **kwargs):
	'''Make Email Queue object'''
	e = frappe.new_doc('Email Queue')
	e.priority = kwargs.get('send_priority')
	attachments = kwargs.get('attachments')
	if attachments:
		# store attachments with fid, to be attached on-demand later
		_attachments = []
		for att in attachments:
			if att.get('fid'):
				_attachments.append(att)
		e.attachments = json.dumps(_attachments)

	try:
		mail = get_email(recipients,
			sender=sender,
			subject=subject,
			formatted=kwargs.get('formatted'),
			text_content=kwargs.get('text_content'),
			attachments=kwargs.get('attachments'),
			reply_to=kwargs.get('reply_to'),
			cc=kwargs.get('cc'),
			email_account=kwargs.get('email_account'),
			expose_recipients=kwargs.get('expose_recipients'),
			inline_images=kwargs.get('inline_images'),
			header=kwargs.get('header'))

		mail.set_message_id(kwargs.get('message_id'),kwargs.get('is_notification'))
		if kwargs.get('read_receipt'):
			mail.msg_root["Disposition-Notification-To"] = sender
		if kwargs.get('in_reply_to'):
			mail.set_in_reply_to(kwargs.get('in_reply_to'))

		e.message_id = mail.msg_root["Message-Id"].strip(" <>")
		e.message = cstr(mail.as_string())
		e.sender = mail.sender

	except frappe.InvalidEmailAddressError:
		# bad Email Address - don't add to queue
		frappe.log_error('Invalid Email ID Sender: {0}, Recipients: {1}'.format(mail.sender,
			', '.join(mail.recipients)), 'Email Not Sent')

	e.set_recipients(recipients + kwargs.get('cc', []))
	e.reference_doctype = kwargs.get('reference_doctype')
	e.reference_name = kwargs.get('reference_name')
	e.add_unsubscribe_link = kwargs.get("add_unsubscribe_link")
	e.unsubscribe_method = kwargs.get('unsubscribe_method')
	e.unsubscribe_params = kwargs.get('unsubscribe_params')
	e.expose_recipients = kwargs.get('expose_recipients')
	e.communication = kwargs.get('communication')
	e.send_after = kwargs.get('send_after')
	e.show_as_cc = ",".join(kwargs.get('cc', []))
	e.insert(ignore_permissions=True)

	return e

def check_email_limit(recipients):
	# if using settings from site_config.json, check email limit
	# No limit for own email settings
	smtp_server = SMTPServer()

	if (smtp_server.email_account
		and getattr(smtp_server.email_account, "from_site_config", False)
		or frappe.flags.in_test):

		monthly_email_limit = frappe.conf.get('limits', {}).get('emails')
		daily_email_limit = cint(frappe.conf.get('limits', {}).get('daily_emails'))

		if frappe.flags.in_test:
			monthly_email_limit = 500
			daily_email_limit = 50

		if daily_email_limit:
			# get count of sent mails in last 24 hours
			today = get_emails_sent_today()
			if (today + len(recipients)) > daily_email_limit:
				throw(_("Cannot send this email. You have crossed the sending limit of {0} emails for this day.").format(daily_email_limit),
					EmailLimitCrossedError)

		if not monthly_email_limit:
			return

		# get count of mails sent this month
		this_month = get_emails_sent_this_month()

		if (this_month + len(recipients)) > monthly_email_limit:
			throw(_("Cannot send this email. You have crossed the sending limit of {0} emails for this month.").format(monthly_email_limit),
				EmailLimitCrossedError)

def get_emails_sent_this_month():
	return frappe.db.sql("""select count(name) from `tabEmail Queue` where
		status='Sent' and MONTH(creation)=MONTH(CURDATE())""")[0][0]

def get_emails_sent_today():
	return frappe.db.sql("""select count(name) from `tabEmail Queue` where
		status='Sent' and creation>DATE_SUB(NOW(), INTERVAL 24 HOUR)""")[0][0]

def get_unsubscribe_message(unsubscribe_message, expose_recipients):
	if unsubscribe_message:
		unsubscribe_html = '''<a href="<!--unsubscribe url-->"
			target="_blank">{0}</a>'''.format(unsubscribe_message)
	else:
		unsubscribe_link = '''<a href="<!--unsubscribe url-->"
			target="_blank">{0}</a>'''.format(_('Unsubscribe'))
		unsubscribe_html = _("{0} to stop receiving emails of this type").format(unsubscribe_link)

	html = """<div class="email-unsubscribe">
			<!--cc message-->
			<div>
				{0}
			</div>
		</div>""".format(unsubscribe_html)

	if expose_recipients == "footer":
		text = "\n<!--cc message-->"
	else:
		text = ""
	text += "\n\n{unsubscribe_message}: <!--unsubscribe url-->\n".format(unsubscribe_message=unsubscribe_message)

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
	frappe.respond_as_web_page(_("Unsubscribed"),
		_("{0} has left the conversation in {1} {2}").format(email, _(doctype), name),
		indicator_color='green')

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

	for i in range(cache.llen('cache_email_queue')):
		email = cache.lpop('cache_email_queue')

		if cint(frappe.defaults.get_defaults().get("hold_queue"))==1:
			break

		if email:
			send_one(email, smtpserver, auto_commit, from_test=from_test)

		# NOTE: removing commit here because we pass auto_commit
		# finally:
		# 	frappe.db.commit()
def make_cache_queue():
	'''cache values in queue before sendign'''
	cache = frappe.cache()

	emails = frappe.db.sql('''select
			name
		from
			`tabEmail Queue`
		where
			(status='Not Sent' or status='Partially Sent') and
			(send_after is null or send_after < %(now)s)
		order
			by priority desc, creation asc
		limit 500''', { 'now': now_datetime() })

	# reset value
	cache.delete_value('cache_email_queue')
	for e in emails:
		cache.rpush('cache_email_queue', e[0])

def send_one(email, smtpserver=None, auto_commit=True, now=False, from_test=False):
	'''Send Email Queue with given smtpserver'''

	email = frappe.db.sql('''select
			name, status, communication, message, sender, reference_doctype,
			reference_name, unsubscribe_param, unsubscribe_method, expose_recipients,
			show_as_cc, add_unsubscribe_link, attachments
		from
			`tabEmail Queue`
		where
			name=%s
		for update''', email, as_dict=True)[0]

	recipients_list = frappe.db.sql('''select name, recipient, status from
		`tabEmail Queue Recipient` where parent=%s''',email.name,as_dict=1)

	if frappe.are_emails_muted():
		frappe.msgprint(_("Emails are muted"))
		return
	if cint(frappe.defaults.get_defaults().get("hold_queue"))==1 :
		return

	if email.status not in ('Not Sent','Partially Sent') :
		# rollback to release lock and return
		frappe.db.rollback()
		return


	frappe.db.sql("""update `tabEmail Queue` set status='Sending', modified=%s where name=%s""",
		(now_datetime(), email.name), auto_commit=auto_commit)

	if email.communication:
		frappe.get_doc('Communication', email.communication).set_delivery_status(commit=auto_commit)

	try:
		if not frappe.flags.in_test:
			if not smtpserver: smtpserver = SMTPServer()
			smtpserver.setup_email_account(email.reference_doctype, sender=email.sender)

		for recipient in recipients_list:
			if recipient.status != "Not Sent":
				continue

			message = prepare_message(email, recipient.recipient, recipients_list)
			if not frappe.flags.in_test:
				smtpserver.sess.sendmail(email.sender, recipient.recipient, encode(message))

			recipient.status = "Sent"
			frappe.db.sql("""update `tabEmail Queue Recipient` set status='Sent', modified=%s where name=%s""",
				(now_datetime(), recipient.name), auto_commit=auto_commit)

		#if all are sent set status
		if any("Sent" == s.status for s in recipients_list):
			frappe.db.sql("""update `tabEmail Queue` set status='Sent', modified=%s where name=%s""",
				(now_datetime(), email.name), auto_commit=auto_commit)
		else:
			frappe.db.sql("""update `tabEmail Queue` set status='Error', error=%s
				where name=%s""", ("No recipients to send to", email.name), auto_commit=auto_commit)
		if frappe.flags.in_test:
			frappe.flags.sent_mail = message
			return
		if email.communication:
			frappe.get_doc('Communication', email.communication).set_delivery_status(commit=auto_commit)

	except (smtplib.SMTPServerDisconnected,
			smtplib.SMTPConnectError,
			smtplib.SMTPHeloError,
			smtplib.SMTPAuthenticationError,
			JobTimeoutException):

		# bad connection/timeout, retry later

		if any("Sent" == s.status for s in recipients_list):
			frappe.db.sql("""update `tabEmail Queue` set status='Partially Sent', modified=%s where name=%s""",
				(now_datetime(), email.name), auto_commit=auto_commit)
		else:
			frappe.db.sql("""update `tabEmail Queue` set status='Not Sent', modified=%s where name=%s""",
				(now_datetime(), email.name), auto_commit=auto_commit)

		if email.communication:
			frappe.get_doc('Communication', email.communication).set_delivery_status(commit=auto_commit)

		# no need to attempt further
		return

	except Exception as e:
		frappe.db.rollback()

		if any("Sent" == s.status for s in recipients_list):
			frappe.db.sql("""update `tabEmail Queue` set status='Partially Errored', error=%s where name=%s""",
				(text_type(e), email.name), auto_commit=auto_commit)
		else:
			frappe.db.sql("""update `tabEmail Queue` set status='Error', error=%s
where name=%s""", (text_type(e), email.name), auto_commit=auto_commit)

		if email.communication:
			frappe.get_doc('Communication', email.communication).set_delivery_status(commit=auto_commit)

		if now:
			print(frappe.get_traceback())
			raise e

		else:
			# log to Error Log
			log('frappe.email.queue.flush', text_type(e))

def prepare_message(email, recipient, recipients_list):
	message = email.message
	if not message:
		return ""

	if email.add_unsubscribe_link and email.reference_doctype: # is missing the check for unsubscribe message but will not add as there will be no unsubscribe url
		unsubscribe_url = get_unsubcribed_url(email.reference_doctype, email.reference_name, recipient,
		email.unsubscribe_method, email.unsubscribe_params)
		message = message.replace("<!--unsubscribe url-->", quopri.encodestring(unsubscribe_url.encode()).decode())

	if email.expose_recipients == "header":
		pass
	else:
		if email.expose_recipients == "footer":
			if isinstance(email.show_as_cc, string_types):
				email.show_as_cc = email.show_as_cc.split(",")
			email_sent_to = [r.recipient for r in recipients_list]
			email_sent_cc = ", ".join([e for e in email_sent_to if e in email.show_as_cc])
			email_sent_to = ", ".join([e for e in email_sent_to if e not in email.show_as_cc])

			if email_sent_cc:
				email_sent_message = _("This email was sent to {0} and copied to {1}").format(email_sent_to,email_sent_cc)
			else:
				email_sent_message = _("This email was sent to {0}").format(email_sent_to)
			message = message.replace("<!--cc message-->", quopri.encodestring(email_sent_message.encode()).decode())

		message = message.replace("<!--recipient-->", recipient)

	message = (message and message.encode('utf8')) or ''
	if not email.attachments:
		return message

	# On-demand attachments
	from email.parser import Parser

	msg_obj = Parser().parsestr(message)
	attachments = json.loads(email.attachments)

	for attachment in attachments:
		if attachment.get('fcontent'): continue

		fid = attachment.get('fid')
		if not fid: continue

		fname, fcontent = get_file(fid)
		attachment.update({
			'fname': fname,
			'fcontent': fcontent,
			'parent': msg_obj
		})
		attachment.pop("fid", None)
		add_attachment(**attachment)

	return msg_obj.as_string()

def clear_outbox():
	"""Remove low priority older than 31 days in Outbox and expire mails not sent for 7 days.
	Called daily via scheduler.
	Note: Used separate query to avoid deadlock
	"""

	email_queues = frappe.db.sql_list("""select name from `tabEmail Queue`
		where priority=0 and datediff(now(), modified) > 31""")

	if email_queues:
		frappe.db.sql("""delete from `tabEmail Queue` where name in (%s)"""
			% ','.join(['%s']*len(email_queues)), tuple(email_queues))

		frappe.db.sql("""delete from `tabEmail Queue Recipient` where parent in (%s)"""
			% ','.join(['%s']*len(email_queues)), tuple(email_queues))

	frappe.db.sql("""
		update `tabEmail Queue`
		set status='Expired'
		where datediff(curdate(), modified) > 7 and status='Not Sent' and (send_after is null or send_after < %(now)s)""", { 'now': now_datetime() })
