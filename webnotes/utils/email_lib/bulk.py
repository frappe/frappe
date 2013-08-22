# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
# MIT License. See license.txt 

from __future__ import unicode_literals
import webnotes
from webnotes.model.doc import Document
from webnotes.utils import cint

class BulkLimitCrossedError(webnotes.ValidationError): pass

def send(recipients=None, sender=None, doctype='Profile', email_field='email',
		subject='[No Subject]', message='[No Content]', ref_doctype=None, ref_docname=None):
	"""send bulk mail if not unsubscribed and within conf.bulk_mail_limit"""
	import webnotes
			
	def is_unsubscribed(rdata):
		if not rdata: return 1
		return cint(rdata.unsubscribed)

	def check_bulk_limit(new_mails):
		import conf, startup
		from webnotes.utils import nowdate
		this_month = webnotes.conn.sql("""select count(*) from `tabBulk Email` where
			month(creation)=month(%s)""" % nowdate())[0][0]

		if hasattr(startup, 'get_monthly_bulk_mail_limit'):
			monthly_bulk_mail_limit = startup.get_monthly_bulk_mail_limit()
		else:
			monthly_bulk_mail_limit = getattr(conf, 'monthly_bulk_mail_limit', 500)

		if this_month + len(recipients) > monthly_bulk_mail_limit:
			webnotes.msgprint("""Monthly Bulk Mail Limit (%s) Crossed""" % monthly_bulk_mail_limit,
				raise_exception=BulkLimitCrossedError)

	def update_message(doc):
		from webnotes.utils import get_request_site_address
		import urllib
		updated = message + """<div style="padding: 7px; border-top: 1px solid #aaa;
			margin-top: 17px;">
			<small><a href="%s/server.py?%s">
			Unsubscribe</a> from this list.</small></div>""" % (get_request_site_address(), 
			urllib.urlencode({
				"cmd": "webnotes.utils.email_lib.bulk.unsubscribe",
				"email": doc.get(email_field),
				"type": doctype,
				"email_field": email_field
			}))
			
		return updated
			
	if not recipients: recipients = []
	if not sender or sender == "Administrator":
		sender = webnotes.conn.get_value('Email Settings', None, 'auto_email_id')
	check_bulk_limit(len(recipients))

	import HTMLParser
	from webnotes.utils.email_lib.html2text import html2text
	
	try:
		text_content = html2text(message)
	except HTMLParser.HTMLParseError:
		text_content = "[See html attachment]"
	
	for r in list(set(recipients)):
		rdata = webnotes.conn.sql("""select * from `tab%s` where %s=%s""" % (doctype, 
			email_field, '%s'), r, as_dict=1)
		
		doc = rdata and rdata[0] or {}
		
		if not is_unsubscribed(doc):
			# add to queue
			add(r, sender, subject, update_message(doc), text_content, ref_doctype, ref_docname)

def add(email, sender, subject, message, text_content=None, ref_doctype=None, ref_docname=None):
	"""add to bulk mail queue"""
	from webnotes.utils.email_lib.smtp import get_email
	
	e = Document('Bulk Email')
	e.sender = sender
	e.recipient = email
	try:
		e.message = get_email(email, sender=e.sender, msg=message, subject=subject, 
			text_content = text_content).as_string()
	except webnotes.ValidationError, e:
		# bad email id - don't add to queue
		return
		
	e.status = 'Not Sent'
	e.ref_doctype = ref_doctype
	e.ref_docname = ref_docname
	e.save()
	
@webnotes.whitelist(allow_guest=True)
def unsubscribe():
	doctype = webnotes.form_dict.get('type')
	field = webnotes.form_dict.get('email_field')
	email = webnotes.form_dict.get('email')

	webnotes.conn.sql("""update `tab%s` set unsubscribed=1
		where `%s`=%s""" % (doctype, field, '%s'), email)
	
	if not webnotes.form_dict.get("from_test"):
		webnotes.conn.commit()

	webnotes.message_title = "Unsubscribe"
	webnotes.message = "<h3>Unsubscribed</h3><p>%s has been successfully unsubscribed.</p>" % email

	webnotes.response['type'] = 'page'
	webnotes.response['page_name'] = 'message.html'
	
def flush(from_test=False):
	"""flush email queue, every time: called from scheduler"""
	import webnotes, conf
	from webnotes.utils.email_lib.smtp import SMTPServer, get_email

	smptserver = SMTPServer()
	
	auto_commit = not from_test
	
	if webnotes.mute_emails or getattr(conf, "mute_emails", False):
		webnotes.msgprint("Emails are muted")
		from_test = True

	for i in xrange(500):		
		email = webnotes.conn.sql("""select * from `tabBulk Email` where 
			status='Not Sent' limit 1 for update""", as_dict=1)
		if email:
			email = email[0]
		else:
			break
			
		webnotes.conn.sql("""update `tabBulk Email` set status='Sending' where name=%s""", 
			email["name"], auto_commit=auto_commit)
		try:
			if not from_test:
				smptserver.sess.sendmail(email["sender"], email["recipient"], email["message"])

			webnotes.conn.sql("""update `tabBulk Email` set status='Sent' where name=%s""", 
				email["name"], auto_commit=auto_commit)

		except Exception, e:
			webnotes.conn.sql("""update `tabBulk Email` set status='Error', error=%s 
				where name=%s""", (unicode(e), email["name"]), auto_commit=auto_commit)

def clear_outbox():
	"""remove mails older than 30 days in Outbox"""
	webnotes.conn.sql("""delete from `tabBulk Email` where
		datediff(now(), creation) > 30""")
