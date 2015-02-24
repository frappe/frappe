# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import json
from email.utils import formataddr
from frappe.website.utils import is_signup_enabled
from frappe.utils import get_url, cstr
from frappe.utils.email_lib.email_body import get_email
from frappe.utils.email_lib.smtp import send
from frappe.utils import scrub_urls, cint, quoted
from frappe import _

from frappe.model.document import Document

class Communication(Document):
	def validate(self):
		if not self.parentfield:
			self.parentfield = "communications"

	def get_parent_doc(self):
		return frappe.get_doc(self.parenttype, self.parent)

	def update_parent(self):
		"""update status of parent Lead or Contact based on who is replying"""
		if self.parenttype and self.parent:
			parent_doc = self.get_parent_doc()
			parent_doc.run_method("on_communication")

	def on_update(self):
		self.update_parent()

@frappe.whitelist()
def make(doctype=None, name=None, content=None, subject=None, sent_or_received = "Sent",
	sender=None, recipients=None, communication_medium="Email", send_email=False,
	print_html=None, print_format=None, attachments='[]', send_me_a_copy=False, set_lead=True, date=None):

	is_error_report = (doctype=="User" and name==frappe.session.user and subject=="Error Report")

	if doctype and name and not is_error_report and not frappe.has_permission(doctype, "email", name):
		raise frappe.PermissionError("You are not allowed to send emails related to: {doctype} {name}".format(
			doctype=doctype, name=name))

	_make(doctype=doctype, name=name, content=content, subject=subject, sent_or_received=sent_or_received,
		sender=sender, recipients=recipients, communication_medium=communication_medium, send_email=send_email,
		print_html=print_html, print_format=print_format, attachments=attachments, send_me_a_copy=send_me_a_copy, set_lead=set_lead,
		date=date)

def _make(doctype=None, name=None, content=None, subject=None, sent_or_received = "Sent",
	sender=None, recipients=None, communication_medium="Email", send_email=False,
	print_html=None, print_format=None, attachments='[]', send_me_a_copy=False, set_lead=True, date=None):

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

	d.idx = cint(frappe.db.sql("""select max(idx) from `tabCommunication`
		where parenttype=%s and parent=%s""", (doctype, name))[0][0]) + 1

	comm.ignore_permissions = True
	comm.insert()

	if send_email:
		d = comm
		send_comm_email(d, name, sent_via, print_html, print_format, attachments, send_me_a_copy)

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

def send_comm_email(d, name, sent_via=None, print_html=None, print_format=None, attachments='[]', send_me_a_copy=False):
	footer = None


	if sent_via:
		if hasattr(sent_via, "get_sender"):
			d.sender = sent_via.get_sender(d) or d.sender
		if hasattr(sent_via, "get_subject"):
			d.subject = sent_via.get_subject(d)
		if hasattr(sent_via, "get_content"):
			d.content = sent_via.get_content(d)

		footer = "<hr>" + set_portal_link(sent_via, d)

	mail = get_email(d.recipients, sender=d.sender, subject=d.subject,
		msg=d.content, footer=footer)

	if send_me_a_copy:
		mail.cc.append(frappe.db.get_value("User", frappe.session.user, "email"))

	if print_html or print_format:
		attach_print(mail, sent_via, print_html, print_format)

	for a in json.loads(attachments):
		try:
			mail.attach_file(a)
		except IOError:
			frappe.throw(_("Unable to find attachment {0}").format(a))

	send(mail)

def attach_print(mail, sent_via, print_html, print_format):
	name = sent_via.name
	if not print_html and print_format:
		print_html = frappe.get_print_format(sent_via.doctype, sent_via.name, print_format)

	print_settings = frappe.db.get_singles_dict("Print Settings")
	send_print_as_pdf = cint(print_settings.send_print_as_pdf)

	if send_print_as_pdf:
		try:
			mail.add_pdf_attachment(name.replace(' ','').replace('/','-') + '.pdf', print_html)
		except Exception:
			frappe.msgprint(_("Error generating PDF, attachment sent as HTML"))
			frappe.errprint(frappe.get_traceback())
			send_print_as_pdf = 0

	if not send_print_as_pdf:
		print_html = scrub_urls(print_html)
		mail.add_attachment(name.replace(' ','').replace('/','-') + '.html',
			print_html, 'text/html')

def set_portal_link(sent_via, comm):
	"""set portal link in footer"""
	footer = ""

	if is_signup_enabled():
		is_valid_recipient = cstr(sent_via.get("email") or sent_via.get("email_id") or
			sent_via.get("contact_email")) in comm.recipients
		if is_valid_recipient:
			url = quoted("%s/%s/%s" % (get_url(), sent_via.doctype, sent_via.name))
			footer = """<!-- Portal Link -->
					<p><a href="%s" target="_blank">View this on our website</a></p>""" % url

	return footer
