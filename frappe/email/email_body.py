# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils.pdf import get_pdf
from frappe.email.smtp import get_outgoing_email_account
from frappe.utils import (get_url, scrub_urls, strip, expand_relative_urls, cint,
	split_emails, to_markdown, markdown, encode, random_string)
import email.utils
from frappe.utils import parse_addr

def get_email(recipients, sender='', msg='', subject='[No Subject]',
	text_content = None, footer=None, print_html=None, formatted=None, attachments=None,
	content=None, reply_to=None, cc=[], email_account=None, expose_recipients=None):
	"""send an html email as multipart with attachments and all"""
	content = content or msg
	emailobj = EMail(sender, recipients, subject, reply_to=reply_to, cc=cc, email_account=email_account, expose_recipients=expose_recipients)

	if not content.strip().startswith("<"):
		content = markdown(content)

	emailobj.set_html(content, text_content, footer=footer, print_html=print_html, formatted=formatted)

	if isinstance(attachments, dict):
		attachments = [attachments]

	for attach in (attachments or []):
		emailobj.add_attachment(**attach)

	return emailobj

class EMail:
	"""
	Wrapper on the email module. Email object represents emails to be sent to the client.
	Also provides a clean way to add binary `FileData` attachments
	Also sets all messages as multipart/alternative for cleaner reading in text-only clients
	"""
	def __init__(self, sender='', recipients=(), subject='', alternative=0, reply_to=None, cc=(), email_account=None, expose_recipients=None):
		from email.mime.multipart import MIMEMultipart
		from email import Charset
		Charset.add_charset('utf-8', Charset.QP, Charset.QP, 'utf-8')

		if isinstance(recipients, basestring):
			recipients = recipients.replace(';', ',').replace('\n', '')
			recipients = split_emails(recipients)

		# remove null
		recipients = filter(None, (strip(r) for r in recipients))

		self.sender = sender
		self.reply_to = reply_to or sender
		self.recipients = recipients
		self.subject = subject
		self.expose_recipients = expose_recipients

		self.msg_root = MIMEMultipart('mixed')
		self.msg_multipart = MIMEMultipart('alternative')
		self.msg_root.attach(self.msg_multipart)
		self.cc = cc or []
		self.html_set = False

		self.email_account = email_account or get_outgoing_email_account()

	def set_html(self, message, text_content = None, footer=None, print_html=None, formatted=None):
		"""Attach message in the html portion of multipart/alternative"""
		if not formatted:
			formatted = get_formatted_html(self.subject, message, footer, print_html, email_account=self.email_account)

		# this is the first html part of a multi-part message,
		# convert to text well
		if not self.html_set:
			if text_content:
				self.set_text(expand_relative_urls(text_content))
			else:
				self.set_html_as_text(expand_relative_urls(formatted))

		self.set_part_html(formatted)
		self.html_set = True

	def set_text(self, message):
		"""
			Attach message in the text portion of multipart/alternative
		"""
		from email.mime.text import MIMEText
		part = MIMEText(message, 'plain', 'utf-8')
		self.msg_multipart.attach(part)

	def set_part_html(self, message):
		from email.mime.text import MIMEText
		part = MIMEText(message, 'html', 'utf-8')
		self.msg_multipart.attach(part)

	def set_html_as_text(self, html):
		"""return html2text"""
		self.set_text(to_markdown(html))

	def set_message(self, message, mime_type='text/html', as_attachment=0, filename='attachment.html'):
		"""Append the message with MIME content to the root node (as attachment)"""
		from email.mime.text import MIMEText

		maintype, subtype = mime_type.split('/')
		part = MIMEText(message, _subtype = subtype)

		if as_attachment:
			part.add_header('Content-Disposition', 'attachment', filename=filename)

		self.msg_root.attach(part)

	def attach_file(self, n):
		"""attach a file from the `FileData` table"""
		from frappe.utils.file_manager import get_file
		res = get_file(n)
		if not res:
			return

		self.add_attachment(res[0], res[1])

	def add_attachment(self, fname, fcontent, content_type=None):
		"""add attachment"""
		from email.mime.audio import MIMEAudio
		from email.mime.base import MIMEBase
		from email.mime.image import MIMEImage
		from email.mime.text import MIMEText

		import mimetypes
		if not content_type:
			content_type, encoding = mimetypes.guess_type(fname)

		if content_type is None:
			# No guess could be made, or the file is encoded (compressed), so
			# use a generic bag-of-bits type.
			content_type = 'application/octet-stream'

		maintype, subtype = content_type.split('/', 1)
		if maintype == 'text':
			# Note: we should handle calculating the charset
			if isinstance(fcontent, unicode):
				fcontent = fcontent.encode("utf-8")
			part = MIMEText(fcontent, _subtype=subtype, _charset="utf-8")
		elif maintype == 'image':
			part = MIMEImage(fcontent, _subtype=subtype)
		elif maintype == 'audio':
			part = MIMEAudio(fcontent, _subtype=subtype)
		else:
			part = MIMEBase(maintype, subtype)
			part.set_payload(fcontent)
			# Encode the payload using Base64
			from email import encoders
			encoders.encode_base64(part)

		# Set the filename parameter
		if fname:
			part.add_header(b'Content-Disposition',
				("attachment; filename=\"%s\"" % fname).encode('utf-8'))

		self.msg_root.attach(part)

	def add_pdf_attachment(self, name, html, options=None):
		self.add_attachment(name, get_pdf(html, options), 'application/octet-stream')

	def validate(self):
		"""validate the Email Addresses"""
		from frappe.utils import validate_email_add

		if not self.sender:
			self.sender = self.email_account.default_sender

		validate_email_add(strip(self.sender), True)
		self.reply_to = validate_email_add(strip(self.reply_to) or self.sender, True)

		self.replace_sender()

		self.recipients = [strip(r) for r in self.recipients]
		self.cc = [strip(r) for r in self.cc]

		for e in self.recipients + (self.cc or []):
			validate_email_add(e, True)

	def replace_sender(self):
		if cint(self.email_account.always_use_account_email_id_as_sender):
			self.set_header('X-Original-From', self.sender)
			sender_name, sender_email = parse_addr(self.sender)
			self.sender = email.utils.formataddr((sender_name or self.email_account.name, self.email_account.email_id))

	def set_message_id(self, message_id, is_notification=False):
		if message_id:
			self.msg_root["Message-Id"] = '<' + message_id + '>'
		else:
			self.msg_root["Message-Id"] = get_message_id()
			self.msg_root["isnotification"] = '<notification>'
		if is_notification:
			self.msg_root["isnotification"] = '<notification>'

	def set_in_reply_to(self, in_reply_to):
		"""Used to send the Message-Id of a received email back as In-Reply-To"""
		self.msg_root["In-Reply-To"] = in_reply_to

	def make(self):
		"""build into msg_root"""
		headers = {
			"Subject":        strip(self.subject),
			"From":           self.sender,
			"To":             ', '.join(self.recipients) if self.expose_recipients=="header" else "<!--recipient-->",
			"Date":           email.utils.formatdate(),
			"Reply-To":       self.reply_to if self.reply_to else None,
			"CC":             ', '.join(self.cc) if self.cc and self.expose_recipients=="header" else None,
			'X-Frappe-Site':  get_url(),
		}

		# reset headers as values may be changed.
		for key, val in headers.iteritems():
			self.set_header(key, val)

		# call hook to enable apps to modify msg_root before sending
		for hook in frappe.get_hooks("make_email_body_message"):
			frappe.get_attr(hook)(self)

	def set_header(self, key, value):
		key = encode(key)
		value = encode(value)

		if self.msg_root.has_key(key):
			del self.msg_root[key]

		self.msg_root[key] = value

	def as_string(self):
		"""validate, build message and convert to string"""
		self.validate()
		self.make()
		return self.msg_root.as_string()

def get_formatted_html(subject, message, footer=None, print_html=None, email_account=None):
	if not email_account:
		email_account = get_outgoing_email_account(False)

	rendered_email = frappe.get_template("templates/emails/standard.html").render({
		"content": message,
		"signature": get_signature(email_account),
		"footer": get_footer(email_account, footer),
		"title": subject,
		"print_html": print_html,
		"subject": subject
	})

	return scrub_urls(rendered_email)

def get_message_id():
	'''Returns Message ID created from doctype and name'''
	return "<{unique}@{site}>".format(
			site=frappe.local.site,
			unique=email.utils.make_msgid(random_string(10)).split('@')[0].split('<')[1])

def get_signature(email_account):
	if email_account and email_account.add_signature and email_account.signature:
		return "<br><br>" + email_account.signature
	else:
		return ""

def get_footer(email_account, footer=None):
	"""append a footer (signature)"""
	footer = footer or ""

	if email_account and email_account.footer:
		footer += '<div style="margin: 15px auto;">{0}</div>'.format(email_account.footer)

	footer += "<!--unsubscribe link here-->"

	company_address = frappe.db.get_default("email_footer_address")

	if company_address:
		footer += '<div style="margin: 15px auto; text-align: center; color: #8d99a6">{0}</div>'\
			.format(company_address.replace("\n", "<br>"))

	if not cint(frappe.db.get_default("disable_standard_email_footer")):
		for default_mail_footer in frappe.get_hooks("default_mail_footer"):
			footer += '<div style="margin: 15px auto;">{0}</div>'.format(default_mail_footer)

	return footer
