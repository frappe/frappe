# ERPNext - web based ERP (http://erpnext.com)
# Copyright (C) 2012 Web Notes Technologies Pvt Ltd
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals
import webnotes

@webnotes.whitelist()
def get_customer_supplier(args=None):
	"""
		Get Customer/Supplier, given a contact, if a unique match exists
	"""
	import webnotes
	if not args: args = webnotes.form_dict
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

@webnotes.whitelist()
def make(doctype=None, name=None, content=None, subject=None, 
	sender=None, recipients=None, contact=None, lead=None, 
	communication_medium="Email", send_email=False, print_html=None,
	attachments='[]', send_me_a_copy=False, set_lead=True):
	# add to Communication

	sent_via = None
	
	d = webnotes.doc('Communication')
	d.subject = subject
	d.content = content
	d.sender = sender or webnotes.conn.get_value("Profile", webnotes.session.user, "email")
	d.recipients = recipients
	d.lead = lead
	d.contact = contact
	if doctype:
		sent_via = webnotes.get_obj(doctype, name)
		d.fields[doctype.replace(" ", "_").lower()] = name
	
	if set_lead:
		set_lead_and_contact(d)
	d.communication_medium = communication_medium
	if send_email:
		send_comm_email(d, name, sent_via, print_html, attachments, send_me_a_copy)
	d.save(1, ignore_fields=True)

def send_comm_email(d, name, sent_via=None, print_html=None, attachments='[]', send_me_a_copy=False):
	from json import loads
	
	if sent_via:
		if hasattr(sent_via, "get_sender"):
			d.sender = sent_via.get_sender(d)
		if hasattr(sent_via, "get_subject"):
			d.subject = sent_via.get_subject(d)
		if hasattr(sent_via, "get_content"):
			d.content = sent_via.get_content(d)

	if not d.sender:
		d.sender = webnotes.session.user

	from webnotes.utils.email_lib.smtp import get_email
	mail = get_email(d.recipients, sender=d.sender, subject=d.subject, 
		msg=d.content)
	
	if send_me_a_copy:
		mail.cc.append(d.sender)
	
	if print_html:
		mail.add_attachment(name.replace(' ','').replace('/','-') + '.html', print_html)

	for a in loads(attachments):
		try:
			mail.attach_file(a)
		except IOError, e:
			webnotes.msgprint("""Unable to find attachment %s. Please resend without attaching this file.""" % a,
				raise_exception=True)
	
	mail.send()
	
	if sent_via and hasattr(sent_via, 'on_communication_sent'):
		sent_via.on_communication_sent(d)

def set_lead_and_contact(d):
	import email.utils
	email_addr = email.utils.parseaddr(d.sender)
	# set contact
	if not d.contact:
		d.contact = webnotes.conn.get_value("Contact", {"email_id": email_addr[1]}, 
			"name") or None

	if not d.lead:
		d.lead = webnotes.conn.get_value("Lead", {"email_id": email_addr[1]}, 
			"name") or None

class DocType():
	def __init__(self, doc, doclist=[]):
		self.doc = doc
		self.doclist = doclist
