# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import HTMLParser
from urllib import quote_plus
from frappe import msgprint, throw, _
from frappe.email.smtp import SMTPServer, get_outgoing_email_account
from frappe.email.email_body import get_email, get_formatted_html
from html2text import html2text
from frappe.utils import get_url, nowdate

class BulkLimitCrossedError(frappe.ValidationError): pass

def send(recipients=None, sender=None, doctype='User', email_field='email',
		subject='[No Subject]', message='[No Content]', ref_doctype=None,
		ref_docname=None, unsubscribe_url=True, attachments=None, reply_to=None):

	if not unsubscribe_url:
		unsubscribe_url = "/api/method/frappe.email.bulk.unsubscribe?doctype={doctype}&name={name}&email={email}"

	def check_bulk_limit(new_mails):
		this_month = frappe.db.sql("""select count(*) from `tabBulk Email` where
			month(creation)=month(%s)""" % nowdate())[0][0]

		# No limit for own email settings
		smtp_server = SMTPServer()
		if smtp_server.email_account and not getattr(smtp_server.email_account,
			"from_site_config", False) or frappe.flags.in_test:
			monthly_bulk_mail_limit = frappe.conf.get('monthly_bulk_mail_limit') or 500

			if (this_month + len(recipients)) > monthly_bulk_mail_limit:
				throw(_("Bulk email limit {0} crossed").format(monthly_bulk_mail_limit),
					BulkLimitCrossedError)

	def update_message(formatted, unsubscribe_url, email):
		updated = formatted
		my_unsubscribe_url = unsubscribe_url.format(email=quote_plus(email), doctype=quote_plus(ref_doctype),
			name=quote_plus(ref_docname))

		unsubscribe_link = """<div style="padding: 7px; border-top: 1px solid #aaa; margin-top: 17px;">
			<small><a href="{base_url}/{url}">{message}</a></small></div>""".format(base_url = get_url(),
				url = my_unsubscribe_url, message = _("Unsubscribe from this list"))

		updated = updated.replace("<!--unsubscribe link here-->", unsubscribe_link)

		return updated

	if not recipients:
		recipients = []

	if not sender or sender == "Administrator":
		email_account = get_outgoing_email_account()
		sender = email_account.get("sender") or email_account.email_id

	check_bulk_limit(len(recipients))

	formatted = get_formatted_html(subject, message)
	unsubscribed = [d.email for d in frappe.db.get_all("Email Unsubscribe", "email",
		{"reference_doctype": ref_doctype, "reference_name": ref_docname})]

	for r in filter(None, list(set(recipients))):
		if r not in unsubscribed:
			# add to queue
			updated = update_message(formatted, unsubscribe_url)
			try:
				text_content = html2text(updated)
			except HTMLParser.HTMLParseError:
				text_content = "[See html attachment]"

			add(r, sender, subject, updated, text_content, ref_doctype, ref_docname, attachments, reply_to)

def add(email, sender, subject, formatted, text_content=None,
	ref_doctype=None, ref_docname=None, attachments=None, reply_to=None):
	"""add to bulk mail queue"""
	e = frappe.new_doc('Bulk Email')
	e.sender = sender
	e.recipient = email

	try:
		e.message = get_email(email, sender=e.sender, formatted=formatted, subject=subject,
			text_content=text_content, attachments=attachments, reply_to=reply_to).as_string()
	except frappe.InvalidEmailAddressError:
		# bad email id - don't add to queue
		return

	e.ref_doctype = ref_doctype
	e.ref_docname = ref_docname
	e.insert(ignore_permissions=True)

@frappe.whitelist(allow_guest=True)
def unsubscribe(doctype, name, email):
	# unsubsribe from comments and communications
	frappe.g

	if not frappe.form_dict.get("from_test"):
		frappe.db.commit()

	return_unsubscribed_page(email)

def return_unsubscribed_page(email):
	frappe.local.message_title = _("Unsubscribed")
	frappe.local.message = "<h3>" + _("Unsubscribed") + "</h3><p>" \
		+ _("{0} has been successfully unsubscribed").fomrat(email) + "</p>"

	frappe.response['type'] = 'page'
	frappe.response['page_name'] = 'message.html'

def flush(from_test=False):
	"""flush email queue, every time: called from scheduler"""
	smtpserver = SMTPServer()

	auto_commit = not from_test

	if frappe.flags.mute_emails or frappe.conf.get("mute_emails") or False:
		msgprint(_("Emails are muted"))
		from_test = True

	for i in xrange(500):
		email = frappe.db.sql("""select * from `tabBulk Email` where
			status='Not Sent' limit 1 for update""", as_dict=1)
		if email:
			email = email[0]
		else:
			break

		frappe.db.sql("""update `tabBulk Email` set status='Sending' where name=%s""",
			(email["name"],), auto_commit=auto_commit)
		try:
			if not from_test:
				smtpserver.sess.sendmail(email["sender"], email["recipient"], email["message"])

			frappe.db.sql("""update `tabBulk Email` set status='Sent' where name=%s""",
				(email["name"],), auto_commit=auto_commit)

		except Exception, e:
			frappe.db.sql("""update `tabBulk Email` set status='Error', error=%s
				where name=%s""", (unicode(e), email["name"]), auto_commit=auto_commit)

def clear_outbox():
	"""remove mails older than 30 days in Outbox"""
	frappe.db.sql("""delete from `tabBulk Email` where
		datediff(now(), creation) > 30""")
