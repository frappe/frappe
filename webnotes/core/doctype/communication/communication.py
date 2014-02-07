# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
import json
import urllib
from email.utils import formataddr
from webnotes.webutils import is_signup_enabled
from webnotes.utils import get_url, cstr
from webnotes.utils.email_lib.email_body import get_email
from webnotes.utils.email_lib.smtp import send

class DocType():
	def __init__(self, doc, doclist=None):
		self.doc = doc
		self.doclist = doclist
		
	def get_parent_bean(self):
		return webnotes.bean(self.doc.parenttype, self.doc.parent)
		
	def update_parent(self):
		"""update status of parent Lead or Contact based on who is replying"""
		observer = self.get_parent_bean().get_attr("on_communication")
		if observer:
			observer()
	
	def on_update(self):
		self.update_parent()

@webnotes.whitelist()
def make(doctype=None, name=None, content=None, subject=None, sent_or_received = "Sent",
	sender=None, recipients=None, communication_medium="Email", send_email=False, 
	print_html=None, attachments='[]', send_me_a_copy=False, set_lead=True, date=None):
	
	if doctype and name and not webnotes.has_permission(doctype, "email", name):
		raise webnotes.PermissionError("You are not allowed to send emails related to: {doctype} {name}".format(
			doctype=doctype, name=name))
			
	_send(doctype=doctype, name=name, content=content, subject=subject, sent_or_received=sent_or_received,
		sender=sender, recipients=recipients, communication_medium=communication_medium, send_email=send_email, 
		print_html=print_html, attachments=attachments, send_me_a_copy=send_me_a_copy, set_lead=set_lead, 
		date=date)
	
def _make(doctype=None, name=None, content=None, subject=None, sent_or_received = "Sent",
	sender=None, recipients=None, communication_medium="Email", send_email=False, 
	print_html=None, attachments='[]', send_me_a_copy=False, set_lead=True, date=None):
	
	# add to Communication
	sent_via = None
	
	# since we are using fullname and email, 
	# if the fullname has any incompatible characters,formataddr can deal with it
	try:
		sender = json.loads(sender)
	except ValueError:
		pass
	
	if isinstance(sender, (tuple, list)) and len(sender)==2:
		sender = formataddr(sender)
	
	comm = webnotes.new_bean('Communication')
	d = comm.doc
	d.subject = subject
	d.content = content
	d.sent_or_received = sent_or_received
	d.sender = sender or webnotes.conn.get_value("Profile", webnotes.session.user, "email")
	d.recipients = recipients
	
	# add as child
	sent_via = webnotes.get_obj(doctype, name)
	d.parent = name
	d.parenttype = doctype
	d.parentfield = "communications"

	if date:
		d.communication_date = date

	d.communication_medium = communication_medium
	
	comm.ignore_permissions = True
	comm.insert()
	
	if send_email:
		d = comm.doc
		send_comm_email(d, name, sent_via, print_html, attachments, send_me_a_copy)

@webnotes.whitelist()
def get_customer_supplier(args=None):
	"""
		Get Customer/Supplier, given a contact, if a unique match exists
	"""
	if not args: args = webnotes.local.form_dict
	if not args.get('contact'):
		raise Exception, "Please specify a contact to fetch Customer/Supplier"
	result = webnotes.conn.sql("""\
		select customer, supplier
		from `tabContact`
		where name = %s""", args.get('contact'), as_dict=1)
	if result and len(result)==1 and (result[0]['customer'] or result[0]['supplier']):
		return {
			'fieldname': result[0]['customer'] and 'customer' or 'supplier',
			'value': result[0]['customer'] or result[0]['supplier']
		}
	return {}

def send_comm_email(d, name, sent_via=None, print_html=None, attachments='[]', send_me_a_copy=False):
	footer = None

	if sent_via:
		if hasattr(sent_via, "get_sender"):
			d.sender = sent_via.get_sender(d) or d.sender
		if hasattr(sent_via, "get_subject"):
			d.subject = sent_via.get_subject(d)
		if hasattr(sent_via, "get_content"):
			d.content = sent_via.get_content(d)
			
		footer = set_portal_link(sent_via, d)
		
	mail = get_email(d.recipients, sender=d.sender, subject=d.subject, 
		msg=d.content, footer=footer)
	
	if send_me_a_copy:
		mail.cc.append(webnotes.conn.get_value("Profile", webnotes.session.user, "email"))
	
	if print_html:
		mail.add_attachment(name.replace(' ','').replace('/','-') + '.html', print_html)

	for a in json.loads(attachments):
		try:
			mail.attach_file(a)
		except IOError, e:
			webnotes.msgprint("""Unable to find attachment %s. Please resend without attaching this file.""" % a,
				raise_exception=True)
	
	send(mail)
	
def set_portal_link(sent_via, comm):
	"""set portal link in footer"""

	footer = None

	if is_signup_enabled() and hasattr(sent_via, "get_portal_page"):
		portal_page = sent_via.get_portal_page()
		if portal_page:
			is_valid_recipient = cstr(sent_via.doc.email or sent_via.doc.email_id or
				sent_via.doc.contact_email) in comm.recipients
			if is_valid_recipient:
				url = "%s/%s?name=%s" % (get_url(), portal_page, urllib.quote(sent_via.doc.name))
				footer = """<!-- Portal Link --><hr>
						<a href="%s" target="_blank">View this on our website</a>""" % url
	
	return footer
