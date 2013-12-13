# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes

class DocType():
	def __init__(self, doc, doclist=[]):
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
	# add to Communication
	sent_via = None
	
	# since we are using fullname and email, 
	# if the fullname has any incompatible characters,formataddr can deal with it
	try:
		import json
		sender = json.loads(sender)
	except ValueError:
		pass
	
	if isinstance(sender, (tuple, list)) and len(sender)==2:
		from email.utils import formataddr
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
	import webnotes
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
	from json import loads
	footer = None

	if sent_via:
		if hasattr(sent_via, "get_sender"):
			d.sender = sent_via.get_sender(d) or d.sender
		if hasattr(sent_via, "get_subject"):
			d.subject = sent_via.get_subject(d)
		if hasattr(sent_via, "get_content"):
			d.content = sent_via.get_content(d)
			
		footer = set_portal_link(sent_via, d)
		
	from webnotes.utils.email_lib.smtp import get_email
	mail = get_email(d.recipients, sender=d.sender, subject=d.subject, 
		msg=d.content, footer=footer)
	
	if send_me_a_copy:
		mail.cc.append(webnotes.conn.get_value("Profile", webnotes.session.user, "email"))
	
	if print_html:
		mail.add_attachment(name.replace(' ','').replace('/','-') + '.html', print_html)

	for a in loads(attachments):
		try:
			mail.attach_file(a)
		except IOError, e:
			webnotes.msgprint("""Unable to find attachment %s. Please resend without attaching this file.""" % a,
				raise_exception=True)
	
	mail.send()
	
def set_portal_link(sent_via, comm):
	"""set portal link in footer"""
	from webnotes.webutils import is_signup_enabled
	from webnotes.utils import get_url, cstr
	import urllib

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

def get_user(doctype, txt, searchfield, start, page_len, filters):
	from erpnext.controllers.queries import get_match_cond
	return webnotes.conn.sql("""select name, concat_ws(' ', first_name, middle_name, last_name) 
			from `tabProfile` 
			where ifnull(enabled, 0)=1 
				and docstatus < 2 
				and (%(key)s like "%(txt)s" 
					or concat_ws(' ', first_name, middle_name, last_name) like "%(txt)s")
				%(mcond)s 
			limit %(start)s, %(page_len)s """ % {'key': searchfield, 
			'txt': "%%%s%%" % txt, 'mcond':get_match_cond(doctype, searchfield),
			'start': start, 'page_len': page_len})

def get_lead(doctype, txt, searchfield, start, page_len, filters):
	from erpnext.controllers.queries import get_match_cond
	return webnotes.conn.sql(""" select name, lead_name from `tabLead` 
			where docstatus < 2 
				and (%(key)s like "%(txt)s" 
					or lead_name like "%(txt)s" 
					or company_name like "%(txt)s") 
				%(mcond)s 
			order by lead_name asc 
			limit %(start)s, %(page_len)s """ % {'key': searchfield,'txt': "%%%s%%" % txt, 
			'mcond':get_match_cond(doctype, searchfield), 'start': start, 
			'page_len': page_len})