# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import HTMLParser
import urllib
from frappe import msgprint, throw, _
from frappe.email.smtp import SMTPServer, get_outgoing_email_account
from frappe.email.email_body import get_email, get_formatted_html
from frappe.email.html2text import html2text
from frappe.utils import cint, get_url, nowdate

class BulkLimitCrossedError(frappe.ValidationError): pass

def send(recipients=None, sender=None, doctype='User', email_field='email',
		subject='[No Subject]', message='[No Content]', ref_doctype=None,
		ref_docname=None, add_unsubscribe_link=True, attachments=None):

	def is_unsubscribed(rdata):
		if not rdata:
			return 1
		return cint(rdata.unsubscribed)

	def check_bulk_limit(new_mails):
		this_month = frappe.db.sql("""select count(*) from `tabBulk Email` where
			month(creation)=month(%s)""" % nowdate())[0][0]

		# No limit for own email settings
		smtp_server = SMTPServer()
		if smtp_server.email_account and not getattr(smtp_server.email_account,
			"from_site_config", False):
			monthly_bulk_mail_limit = frappe.conf.get('monthly_bulk_mail_limit') or 500

			if (this_month + len(recipients)) > monthly_bulk_mail_limit:
				throw(_("Bulk email limit {0} crossed").format(monthly_bulk_mail_limit),
					BulkLimitCrossedError)

	def update_message(formatted, doc, add_unsubscribe_link):
		updated = formatted
		if add_unsubscribe_link:
			unsubscribe_link = """<div style="padding: 7px; border-top: 1px solid #aaa;
				margin-top: 17px;">
				<small><a href="%s/?%s">
				Unsubscribe</a> from this list.</small></div>""" % (get_url(),
				urllib.urlencode({
					"cmd": "frappe.email.bulk.unsubscribe",
					"email": doc.get(email_field),
					"type": doctype,
					"email_field": email_field
				}))

			updated = updated.replace("<!--unsubscribe link here-->", unsubscribe_link)

		return updated

	if not recipients: recipients = []
	if not sender or sender == "Administrator":
		email_account = get_outgoing_email_account()
		sender = email_account.get("sender") or email_account.email_id
	check_bulk_limit(len(recipients))

	formatted = get_formatted_html(subject, message)

	for r in filter(None, list(set(recipients))):
		rdata = frappe.db.sql("""select * from `tab%s` where %s=%s""" % (doctype,
			email_field, '%s'), (r,), as_dict=1)

		doc = rdata and rdata[0] or {}

		if (not add_unsubscribe_link) or (not is_unsubscribed(doc)):
			# add to queue
			updated = update_message(formatted, doc, add_unsubscribe_link)
			try:
				text_content = html2text(updated)
			except HTMLParser.HTMLParseError:
				text_content = "[See html attachment]"

			add(r, sender, subject, updated, text_content, ref_doctype, ref_docname, attachments)

def add(email, sender, subject, formatted, text_content=None,
	ref_doctype=None, ref_docname=None, attachments=None):
	"""add to bulk mail queue"""
	e = frappe.new_doc('Bulk Email')
	e.sender = sender
	e.recipient = email
	try:
		e.message = get_email(email, sender=e.sender, formatted=formatted, subject=subject,
			text_content=text_content, attachments=attachments).as_string()
	except frappe.InvalidEmailAddressError:
		# bad email id - don't add to queue
		return

	e.status = 'Not Sent'
	e.ref_doctype = ref_doctype
	e.ref_docname = ref_docname
	e.save(ignore_permissions=True)

@frappe.whitelist(allow_guest=True)
def unsubscribe():
	doctype = frappe.form_dict.get('type')
	field = frappe.form_dict.get('email_field')
	email = frappe.form_dict.get('email')

	frappe.db.sql("""update `tab%s` set unsubscribed=1
		where `%s`=%s""" % (doctype, field, '%s'), (email,))

	if not frappe.form_dict.get("from_test"):
		frappe.db.commit()

	frappe.local.message_title = "Unsubscribe"
	frappe.local.message = "<h3>Unsubscribed</h3><p>%s has been successfully unsubscribed.</p>" % email

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
