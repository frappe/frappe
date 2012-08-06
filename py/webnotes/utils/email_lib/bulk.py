# Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
# 
# MIT License (MIT)
# 
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# 

from __future__ import unicode_literals
import webnotes

class BulkLimitCrossedError(webnotes.ValidationError): pass

def send(recipients=[], doctype='Profile', email_field='email', first_name_field="first_name",
				last_name_field="last_name", subject='[No Subject]', message='[No Content]'):
	"""send bulk mail if not unsubscribed and within conf.bulk_mail_limit"""
	import webnotes
	def is_unsubscribed(rdata):
		if not rdata: return 1
		return rdata[0]['unsubscribed']

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

	def add_unsubscribe_link(email):
		from webnotes.utils import get_request_site_address
		return message + """<div style="padding: 7px; border-top: 1px solid #aaa;
			margin-top: 17px;">
			<small><a href="http://%s/server.py?cmd=%s&email=%s&type=%s&email_field=%s">
			Unsubscribe</a> from this list.</small></div>""" % (get_request_site_address(), 
			'webnotes.utils.email_lib.bulk.unsubscribe', email, doctype, email_field)

	def full_name(rdata):
		fname = rdata[0].get(first_name_field, '')
		lname = rdata[0].get(last_name_field, '')
		if fname and not lname:
			return fname
		elif lname and not fname:
			return lname
		elif fname and lname:
			return fname + ' ' + lname
		else:
			return rdata[0][email_field].split('@')[0].title()
		
	check_bulk_limit(len(recipients))
	sender = webnotes.conn.get_value('Email Settings', None, 'auto_mail_id')

	for r in recipients:
		rdata = webnotes.conn.sql("""select * from `tab%s` where %s=%s""" % (doctype, 
			email_field, '%s'), r, as_dict=1)
		if not is_unsubscribed(rdata):
			# add to queue
			add(r, sender, subject, add_unsubscribe_link(r) % {"full_name":full_name(rdata)})

def add(email, sender, subject, message):
	"""add to bulk mail queue"""
	from webnotes.model.doc import Document
	from webnotes.utils.email_lib.smtp import get_email
	
	e = Document('Bulk Email')
	e.sender = sender
	e.recipient = email
	e.message = get_email(email, sender=e.sender, msg=message, subject=subject).as_string()
	e.status = 'Not Sent'
	e.save()

@webnotes.whitelist(allow_guest=True)
def unsubscribe():
	doctype = webnotes.form_dict.get('type')
	field = webnotes.form_dict.get('email_field')
	email = webnotes.form_dict.get('email')
	webnotes.conn.sql("""update `tab%s` set unsubscribed=1 
		where email_id=%s""" % (doctype, '%s'), email)
	
	webnotes.unsubscribed_email = email
	webnotes.response['type'] = 'page'
	webnotes.response['page_name'] = 'unsubscribed.html'
	
def flush():
	"""flush email queue, every time: called from scheduler"""
	import webnotes
	from webnotes.utils.email_lib.smtp import SMTPServer
	
	smptserver = SMTPServer()

	for email in webnotes.conn.sql("""select * from `tabBulk Email` where status='Not Sent'""", 
		as_dict=1):
		webnotes.conn.sql("""update `tabBulk Email` set status='Sending' where name=%s""", 
			email["name"], auto_commit=True)
		try:
			smptserver.sess.sendmail(email["sender"], email["recipient"], email["message"])
			webnotes.conn.sql("""update `tabBulk Email` set status='Sent' where name=%s""", 
				email["name"], auto_commit=True)
		except Exception, e:
			webnotes.conn.sql("""update `tabBulk Email` set status='Error', error=%s 
				where name=%s""", (str(e), email["name"]), auto_commit=True)

def clear_outbox():
	"""remove mails older than 30 days in Outbox"""
	webnotes.conn.sql("""delete from `tabBulk Email` where
		datediff(now(), creation) > 30""")
