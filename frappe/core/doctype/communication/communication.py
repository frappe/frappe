# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import json
import urllib
from frappe.website.utils import is_signup_enabled
from frappe.utils import get_url, cstr, cint, scrub_urls
from frappe.email.email_body import get_email
import frappe.email.smtp
from frappe import _

from frappe.model.document import Document

class Communication(Document):
	def validate(self):
		if not self.sender:
			self.sender = frappe.db.get_value("User", frappe.session.user, "email")

	def get_parent_doc(self):
		if not hasattr(self, "parent_doc"):
			if self.reference_doctype and self.reference_name:
				self.parent_doc = frappe.get_doc(self.reference_doctype, self.reference_name)
			else:
				self.parent_doc = None
		return self.parent_doc

	def on_update(self):
		self.update_parent()

	def update_parent(self):
		"""update status of parent Lead or Contact based on who is replying"""
		parent = self.get_parent_doc()
		if not parent:
			return

		status_field = parent.meta.get_field("status")

		if status_field and "Open" in (status_field.options or "").split("\n"):
			frappe.db.set_value(parent.doctype, parent.name, "status",
				"Open" if self.sent_or_received=="Received" else "Replied")

	def send(self, send_me_a_copy=False, print_html=None, print_format=None,
		attachments=None):
		mail = get_email(self.recipients, sender=self.sender, subject=self.subject,
			content=self.content)

		mail.set_message_id(self.name)

		if send_me_a_copy:
			mail.cc.append(frappe.db.get_value("User", frappe.session.user, "email"))

		if print_html or print_format:
			attach_print(mail, self.get_parent_doc(), print_html, print_format)

		if isinstance(attachments, basestring):
			attachments = json.loads(attachments)

		for a in attachments:
			try:
				mail.attach_file(a)
			except IOError:
				frappe.throw(_("Unable to find attachment {0}").format(a))

		frappe.email.smtp.send(mail)

def on_doctype_update():
	frappe.db.add_index("Communication", ["reference_doctype", "reference_name"])

@frappe.whitelist()
def make(doctype=None, name=None, content=None, subject=None, sent_or_received = "Sent",
	sender=None, recipients=None, communication_medium="Email", send_email=False,
	print_html=None, print_format=None, attachments='[]', send_me_a_copy=False, set_lead=True, date=None):

	if doctype and name and not frappe.has_permission(doctype, "email", name):
		raise frappe.PermissionError("You are not allowed to send emails related to: {doctype} {name}".format(
			doctype=doctype, name=name))

	comm = frappe.get_doc({
		"doctype":"Communication",
		"subject": subject,
		"content": content,
		"sender": sender,
		"recipients": recipients,
		"communication_medium": "Email",
		"sent_or_received": sent_or_received,
	})
	comm.insert(ignore_permissions=True)

	if send_email:
		comm.send(send_me_a_copy, print_html, print_format, attachments)

def attach_print(mail, parent_doc, print_html, print_format):
	name = parent_doc.name if parent_doc else "attachment"
	if (not print_html) and parent_doc and print_format:
		print_html = frappe.get_print_format(parent_doc.doctype, parent_doc.name, print_format)

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

	if is_signup_enabled() and hasattr(sent_via, "get_portal_page"):
		portal_page = sent_via.get_portal_page()
		if portal_page:
			is_valid_recipient = cstr(sent_via.get("email") or sent_via.get("email_id") or
				sent_via.get("contact_email")) in comm.recipients
			if is_valid_recipient:
				url = "%s/%s?name=%s" % (get_url(), portal_page, urllib.quote(sent_via.name))
				footer = """<!-- Portal Link -->
						<p><a href="%s" target="_blank">View this on our website</a></p>""" % url

	return footer
