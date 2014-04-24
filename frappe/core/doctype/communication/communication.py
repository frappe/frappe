# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import json
import urllib
from email.utils import formataddr
from frappe.website.utils import is_signup_enabled
from frappe.utils import get_url, cstr
from frappe.utils.email_lib.email_body import get_email
from frappe.utils.email_lib.smtp import send
from frappe.utils import scrub_urls
from frappe import _

from frappe.model.document import Document

class Communication(Document):
	def get_parent_doc(self):
		return frappe.get_doc(self.parenttype, self.parent)

	def update_parent(self):
		"""update status of parent Lead or Contact based on who is replying"""
		observer = getattr(self.get_parent_doc(), "on_communication", None)
		if observer:
			observer()

	def on_update(self):
		self.update_parent()

@frappe.whitelist()
def make(doctype=None, name=None, content=None, subject=None, sent_or_received = "Sent",
	sender=None, recipients=None, communication_medium="Email", send_email=False,
	print_html=None, attachments='[]', send_me_a_copy=False, set_lead=True, date=None):

	if doctype and name and not frappe.has_permission(doctype, "email", name):
		raise frappe.PermissionError("You are not allowed to send emails related to: {doctype} {name}".format(
			doctype=doctype, name=name))

	_make(doctype=doctype, name=name, content=content, subject=subject, sent_or_received=sent_or_received,
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

	comm = frappe.new_doc('Communication')
	d = comm
	d.subject = subject
	d.content = content
	d.sent_or_received = sent_or_received
	d.sender = sender or frappe.db.get_value("User", frappe.session.user, "email")
	d.recipients = recipients

	# add as child
	sent_via = frappe.get_doc(doctype, name)
	d.parent = name
	d.parenttype = doctype
	d.parentfield = "communications"

	if date:
		d.communication_date = date

	d.communication_medium = communication_medium

	comm.ignore_permissions = True
	comm.insert()

	if send_email:
		d = comm
		send_comm_email(d, name, sent_via, print_html, attachments, send_me_a_copy)

@frappe.whitelist()
def get_customer_supplier(args=None):
	"""
		Get Customer/Supplier, given a contact, if a unique match exists
	"""
	if not args: args = frappe.local.form_dict
	if not args.get('contact'):
		raise Exception, "Please specify a contact to fetch Customer/Supplier"
	result = frappe.db.sql("""\
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

	send_print_in_body = frappe.db.get_value("Outgoing Email Settings", None, "send_print_in_body_and_attachment")
	if not send_print_in_body:
		d.content += "<p>Please see attachment for document details.</p>"

	mail = get_email(d.recipients, sender=d.sender, subject=d.subject,
		msg=d.content, footer=footer, print_html=print_html if send_print_in_body else None)

	if send_me_a_copy:
		mail.cc.append(frappe.db.get_value("User", frappe.session.user, "email"))

	if print_html:
		print_html = scrub_urls(print_html)
		mail.add_attachment(name.replace(' ','').replace('/','-') + '.html', print_html)

	for a in json.loads(attachments):
		try:
			mail.attach_file(a)
		except IOError:
			frappe.throw(_("Unable to find attachment {0}").format(a))

	send(mail)

def set_portal_link(sent_via, comm):
	"""set portal link in footer"""

	footer = None

	if is_signup_enabled() and hasattr(sent_via, "get_portal_page"):
		portal_page = sent_via.get_portal_page()
		if portal_page:
			is_valid_recipient = cstr(sent_via.get("email") or sent_via.get("email_id") or
				sent_via.get("contact_email")) in comm.recipients
			if is_valid_recipient:
				url = "%s/%s?name=%s" % (get_url(), portal_page, urllib.quote(sent_via.name))
				footer = """<!-- Portal Link --><hr>
						<a href="%s" target="_blank">View this on our website</a>""" % url

	return footer
