# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import msgprint, throw, _
from frappe.utils import scrub_urls, get_url, strip
from frappe.utils.pdf import get_pdf
import email.utils
from markdown2 import markdown


def get_email(recipients, sender='', msg='', subject='[No Subject]',
	text_content = None, footer=None, print_html=None, formatted=None, attachments=None):
	"""send an html email as multipart with attachments and all"""
	emailobj = EMail(sender, recipients, subject)
	msg = markdown(msg)
	emailobj.set_html(msg, text_content, footer=footer, print_html=print_html, formatted=formatted)

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
	def __init__(self, sender='', recipients=(), subject='', alternative=0, reply_to=None):
		from email.mime.multipart import MIMEMultipart
		from email import Charset
		Charset.add_charset('utf-8', Charset.QP, Charset.QP, 'utf-8')

		if isinstance(recipients, basestring):
			recipients = recipients.replace(';', ',').replace('\n', '')
			recipients = recipients.split(',')

		# remove null
		recipients = filter(None, (strip(r) for r in recipients))

		self.sender = sender
		self.reply_to = reply_to or sender
		self.recipients = recipients
		self.subject = subject

		self.msg_root = MIMEMultipart('mixed')
		self.msg_multipart = MIMEMultipart('alternative')
		self.msg_root.attach(self.msg_multipart)
		self.cc = []
		self.html_set = False

	def set_html(self, message, text_content = None, footer=None, print_html=None, formatted=None):
		"""Attach message in the html portion of multipart/alternative"""
		if not formatted:
			formatted = get_formatted_html(self.subject, message, footer, print_html)

		# this is the first html part of a multi-part message,
		# convert to text well
		if not self.html_set:
			if text_content:
				self.set_text(text_content)
			else:
				self.set_html_as_text(formatted)

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
		import HTMLParser
		from frappe.utils.email_lib.html2text import html2text
		try:
			self.set_text(html2text(html))
		except HTMLParser.HTMLParseError:
			pass

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
		"""validate the email ids"""
		from frappe.utils import validate_email_add
		def _validate(email):
			"""validate an email field"""
			if email and not validate_email_add(email):
				throw(_("{0} is not a valid email id").format(email), frappe.InvalidEmailAddressError)
			return email

		if not self.sender:
			self.sender = frappe.db.get_value('Outgoing Email Settings', None,
				'auto_email_id') or frappe.conf.get('auto_email_id') or None
			if not self.sender:
				msg = _("Please specify 'Auto Email Id' in Setup > Outgoing Email Settings")
				msgprint(msg)
				if not "expires_on" in frappe.conf:
					msgprint(_("Alternatively, you can also specify 'auto_email_id' in site_config.json"))
				raise frappe.ValidationError, msg

		self.sender = _validate(strip(self.sender))
		self.reply_to = _validate(strip(self.reply_to) or self.sender)

		self.recipients = [strip(r) for r in self.recipients]
		self.cc = [strip(r) for r in self.cc]

		for e in self.recipients + (self.cc or []):
			_validate(e)

	def make(self):
		"""build into msg_root"""
		self.msg_root['Subject'] = strip(self.subject).encode("utf-8")
		self.msg_root['From'] = self.sender.encode("utf-8")
		self.msg_root['To'] = ', '.join(self.recipients).encode("utf-8")
		self.msg_root['Date'] = email.utils.formatdate()
		self.msg_root['Reply-To'] = self.reply_to.encode("utf-8")
		if self.cc:
			self.msg_root['CC'] = ', '.join(self.cc).encode("utf-8")

		# add frappe site header
		self.msg_root.add_header(b'X-Frappe-Site', get_url().encode('utf-8'))

	def as_string(self):
		"""validate, build message and convert to string"""
		self.validate()
		self.make()
		return self.msg_root.as_string()

def get_formatted_html(subject, message, footer=None, print_html=None):
	# imported here to avoid cyclic import

	message = scrub_urls(message)
	rendered_email = frappe.get_template("templates/emails/standard.html").render({
		"content": message,
		"footer": get_footer(footer),
		"title": subject,
		"print_html": print_html,
		"subject": subject
	})

	return rendered_email

def get_footer(footer=None):
	"""append a footer (signature)"""
	footer = footer or ""

	# hooks
	for f in frappe.get_hooks("mail_footer"):
		# mail_footer could be a function that returns a value
		mail_footer = frappe.get_attr(f)
		footer += (mail_footer if isinstance(mail_footer, basestring) else mail_footer())

	footer += "<!--unsubscribe link here-->"

	return footer
