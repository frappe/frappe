# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import email.utils
import os
import re
from email import policy
from email.header import Header
from email.mime.multipart import MIMEMultipart

from six import iteritems, string_types, text_type

import frappe
from frappe.email.smtp import get_outgoing_email_account
from frappe.utils import (
	cint,
	expand_relative_urls,
	get_url,
	markdown,
	parse_addr,
	random_string,
	scrub_urls,
	split_emails,
	strip,
	to_markdown,
)
from frappe.utils.pdf import get_pdf


def get_email(
	recipients,
	sender="",
	msg="",
	subject="[No Subject]",
	text_content=None,
	footer=None,
	print_html=None,
	formatted=None,
	attachments=None,
	content=None,
	reply_to=None,
	cc=None,
	bcc=None,
	email_account=None,
	expose_recipients=None,
	inline_images=None,
	header=None,
):
	"""Prepare an email with the following format:
	- multipart/mixed
	        - multipart/alternative
	                - text/plain
	                - multipart/related
	                        - text/html
	                        - inline image
	                - attachment
	"""
	content = content or msg

	if cc is None:
		cc = []
	if bcc is None:
		bcc = []
	if inline_images is None:
		inline_images = []

	emailobj = EMail(
		sender,
		recipients,
		subject,
		reply_to=reply_to,
		cc=cc,
		bcc=bcc,
		email_account=email_account,
		expose_recipients=expose_recipients,
	)

	if not content.strip().startswith("<"):
		content = markdown(content)

	emailobj.set_html(
		content,
		text_content,
		footer=footer,
		header=header,
		print_html=print_html,
		formatted=formatted,
		inline_images=inline_images,
	)

	if isinstance(attachments, dict):
		attachments = [attachments]

	for attach in attachments or []:
		# cannot attach if no filecontent
		if attach.get("fcontent") is None:
			continue
		emailobj.add_attachment(**attach)

	return emailobj


class EMail:
	"""
	Wrapper on the email module. Email object represents emails to be sent to the client.
	Also provides a clean way to add binary `FileData` attachments
	Also sets all messages as multipart/alternative for cleaner reading in text-only clients
	"""

	def __init__(
		self,
		sender="",
		recipients=(),
		subject="",
		alternative=0,
		reply_to=None,
		cc=(),
		bcc=(),
		email_account=None,
		expose_recipients=None,
	):
		from email import charset as Charset

		Charset.add_charset("utf-8", Charset.QP, Charset.QP, "utf-8")

		if isinstance(recipients, string_types):
			recipients = recipients.replace(";", ",").replace("\n", "")
			recipients = split_emails(recipients)

		# remove null
		recipients = filter(None, (strip(r) for r in recipients))

		self.sender = sender
		self.reply_to = reply_to or sender
		self.recipients = recipients
		self.subject = subject
		self.expose_recipients = expose_recipients

		self.msg_root = MIMEMultipart("mixed", policy=policy.SMTPUTF8)
		self.msg_alternative = MIMEMultipart("alternative", policy=policy.SMTPUTF8)
		self.msg_root.attach(self.msg_alternative)
		self.cc = cc or []
		self.bcc = bcc or []
		self.html_set = False

		self.email_account = email_account or get_outgoing_email_account(sender=sender)

	def set_html(
		self,
		message,
		text_content=None,
		footer=None,
		print_html=None,
		formatted=None,
		inline_images=None,
		header=None,
	):
		"""Attach message in the html portion of multipart/alternative"""
		if not formatted:
			formatted = get_formatted_html(
				self.subject,
				message,
				footer,
				print_html,
				email_account=self.email_account,
				header=header,
				sender=self.sender,
			)

		# this is the first html part of a multi-part message,
		# convert to text well
		if not self.html_set:
			if text_content:
				self.set_text(expand_relative_urls(text_content))
			else:
				self.set_html_as_text(expand_relative_urls(formatted))

		self.set_part_html(formatted, inline_images)
		self.html_set = True

	def set_text(self, message):
		"""
		Attach message in the text portion of multipart/alternative
		"""
		from email.mime.text import MIMEText

		part = MIMEText(message, "plain", "utf-8", policy=policy.SMTPUTF8)
		self.msg_alternative.attach(part)

	def set_part_html(self, message, inline_images):
		from email.mime.text import MIMEText

		has_inline_images = re.search("""embed=['"].*?['"]""", message)

		if has_inline_images:
			# process inline images
			message, _inline_images = replace_filename_with_cid(message)

			# prepare parts
			msg_related = MIMEMultipart("related", policy=policy.SMTPUTF8)

			html_part = MIMEText(message, "html", "utf-8", policy=policy.SMTPUTF8)
			msg_related.attach(html_part)

			for image in _inline_images:
				self.add_attachment(
					image.get("filename"),
					image.get("filecontent"),
					content_id=image.get("content_id"),
					parent=msg_related,
					inline=True,
				)

			self.msg_alternative.attach(msg_related)
		else:
			self.msg_alternative.attach(MIMEText(message, "html", "utf-8", policy=policy.SMTPUTF8))

	def set_html_as_text(self, html):
		"""Set plain text from HTML"""
		self.set_text(to_markdown(html))

	def set_message(
		self, message, mime_type="text/html", as_attachment=0, filename="attachment.html"
	):
		"""Append the message with MIME content to the root node (as attachment)"""
		from email.mime.text import MIMEText

		maintype, subtype = mime_type.split("/")
		part = MIMEText(message, _subtype=subtype, policy=policy.SMTPUTF8)

		if as_attachment:
			part.add_header("Content-Disposition", "attachment", filename=filename)

		self.msg_root.attach(part)

	def attach_file(self, n):
		"""attach a file from the `FileData` table"""
		_file = frappe.get_doc("File", {"file_name": n})
		content = _file.get_content()
		if not content:
			return

		self.add_attachment(_file.file_name, content)

	def add_attachment(
		self, fname, fcontent, content_type=None, parent=None, content_id=None, inline=False
	):
		"""add attachment"""

		if not parent:
			parent = self.msg_root

		add_attachment(fname, fcontent, content_type, parent, content_id, inline)

	def add_pdf_attachment(self, name, html, options=None):
		self.add_attachment(name, get_pdf(html, options), "application/octet-stream")

	def validate(self):
		"""validate the Email Addresses"""
		from frappe.utils import validate_email_address

		if not self.sender:
			self.sender = self.email_account.default_sender

		validate_email_address(strip(self.sender), True)
		self.reply_to = validate_email_address(strip(self.reply_to) or self.sender, True)

		self.replace_sender()
		self.replace_sender_name()

		self.recipients = [strip(r) for r in self.recipients]
		self.cc = [strip(r) for r in self.cc]
		self.bcc = [strip(r) for r in self.bcc]

		for e in self.recipients + (self.cc or []) + (self.bcc or []):
			validate_email_address(e, True)

	def replace_sender(self):
		if cint(self.email_account.always_use_account_email_id_as_sender):
			self.set_header("X-Original-From", self.sender)
			sender_name, sender_email = parse_addr(self.sender)
			self.sender = email.utils.formataddr(
				(str(Header(sender_name or self.email_account.name, "utf-8")), self.email_account.email_id)
			)

	def replace_sender_name(self):
		if cint(self.email_account.always_use_account_name_as_sender_name):
			self.set_header("X-Original-From", self.sender)
			sender_name, sender_email = parse_addr(self.sender)
			self.sender = email.utils.formataddr(
				(str(Header(self.email_account.name, "utf-8")), sender_email)
			)

	def set_message_id(self, message_id, is_notification=False):
		if message_id:
			message_id = "<" + message_id + ">"
		else:
			message_id = get_message_id()
			self.set_header("isnotification", "<notification>")

		if is_notification:
			self.set_header("isnotification", "<notification>")

		self.set_header("Message-Id", message_id)

	def set_in_reply_to(self, in_reply_to):
		"""Used to send the Message-Id of a received email back as In-Reply-To"""
		self.set_header("In-Reply-To", in_reply_to)

	def make(self):
		"""build into msg_root"""
		headers = {
			"Subject": strip(self.subject),
			"From": self.sender,
			"To": ", ".join(self.recipients) if self.expose_recipients == "header" else "<!--recipient-->",
			"Date": email.utils.formatdate(),
			"Reply-To": self.reply_to if self.reply_to else None,
			"CC": ", ".join(self.cc) if self.cc and self.expose_recipients == "header" else None,
			"X-Frappe-Site": get_url(),
		}

		# reset headers as values may be changed.
		for key, val in iteritems(headers):
			if val:
				self.set_header(key, val)

		# call hook to enable apps to modify msg_root before sending
		for hook in frappe.get_hooks("make_email_body_message"):
			frappe.get_attr(hook)(self)

	def set_header(self, key, value):
		if key in self.msg_root:
			# delete key if found
			# this is done because adding the same key doesn't override
			# the existing key, rather appends another header with same key.
			del self.msg_root[key]

		self.msg_root[key] = sanitize_email_header(value)

	def as_string(self):
		"""validate, build message and convert to string"""
		self.validate()
		self.make()
		return self.msg_root.as_string(policy=policy.SMTPUTF8)


def get_formatted_html(
	subject,
	message,
	footer=None,
	print_html=None,
	email_account=None,
	header=None,
	unsubscribe_link=None,
	sender=None,
	with_container=False,
):
	if not email_account:
		email_account = get_outgoing_email_account(False, sender=sender)

	rendered_email = frappe.get_template("templates/emails/standard.html").render(
		{
			"brand_logo": get_brand_logo(email_account) if with_container or header else None,
			"with_container": with_container,
			"site_url": get_url(),
			"header": get_header(header),
			"content": message,
			"footer": get_footer(email_account, footer),
			"title": subject,
			"print_html": print_html,
			"subject": subject,
		}
	)

	html = scrub_urls(rendered_email)

	if unsubscribe_link:
		html = html.replace("<!--unsubscribe_link_here-->", unsubscribe_link.html)

	return inline_style_in_html(html)


@frappe.whitelist()
def get_email_html(template, args, subject, header=None, with_container=False):
	import json

	with_container = cint(with_container)
	args = json.loads(args)
	if header and header.startswith("["):
		header = json.loads(header)
	email = frappe.utils.jinja.get_email_from_template(template, args)
	return get_formatted_html(subject, email[0], header=header, with_container=with_container)


def inline_style_in_html(html):
	"""Convert email.css and html to inline-styled html"""
	from premailer import Premailer

	apps = frappe.get_installed_apps()

	# add frappe email css file
	css_files = ["assets/css/email.css"]
	if "frappe" in apps:
		apps.remove("frappe")

	for app in apps:
		path = "assets/{0}/css/email.css".format(app)
		css_files.append(path)

	css_files = [css_file for css_file in css_files if os.path.exists(os.path.abspath(css_file))]

	p = Premailer(html=html, external_styles=css_files, strip_important=False)

	return p.transform()


def add_attachment(fname, fcontent, content_type=None, parent=None, content_id=None, inline=False):
	"""Add attachment to parent which must an email object"""
	import mimetypes
	from email.mime.audio import MIMEAudio
	from email.mime.base import MIMEBase
	from email.mime.image import MIMEImage
	from email.mime.text import MIMEText

	if not content_type:
		content_type, encoding = mimetypes.guess_type(fname)

	if not parent:
		return

	if content_type is None:
		# No guess could be made, or the file is encoded (compressed), so
		# use a generic bag-of-bits type.
		content_type = "application/octet-stream"

	maintype, subtype = content_type.split("/", 1)
	if maintype == "text":
		# Note: we should handle calculating the charset
		if isinstance(fcontent, text_type):
			fcontent = fcontent.encode("utf-8")
		part = MIMEText(fcontent, _subtype=subtype, _charset="utf-8")
	elif maintype == "image":
		part = MIMEImage(fcontent, _subtype=subtype)
	elif maintype == "audio":
		part = MIMEAudio(fcontent, _subtype=subtype)
	else:
		part = MIMEBase(maintype, subtype)
		part.set_payload(fcontent)
		# Encode the payload using Base64
		from email import encoders

		encoders.encode_base64(part)

	# Set the filename parameter
	if fname:
		attachment_type = "inline" if inline else "attachment"
		part.add_header("Content-Disposition", attachment_type, filename=text_type(fname))
	if content_id:
		part.add_header("Content-ID", "<{0}>".format(content_id))

	parent.attach(part)


def get_message_id():
	"""Returns Message ID created from doctype and name"""
	return "<{unique}@{site}>".format(
		site=frappe.local.site,
		unique=email.utils.make_msgid(random_string(10)).split("@")[0].split("<")[1],
	)


def get_signature(email_account):
	if email_account and email_account.add_signature and email_account.signature:
		return "<br>" + email_account.signature
	else:
		return ""


def get_footer(email_account, footer=None):
	"""append a footer (signature)"""
	footer = footer or ""

	args = {}

	if email_account and email_account.footer:
		args.update({"email_account_footer": email_account.footer})

	sender_address = frappe.db.get_default("email_footer_address")

	if sender_address:
		args.update({"sender_address": sender_address})

	if not cint(frappe.db.get_default("disable_standard_email_footer")):
		args.update({"default_mail_footer": frappe.get_hooks("default_mail_footer")})

	footer += frappe.utils.jinja.get_email_from_template("email_footer", args)[0]

	return footer


def replace_filename_with_cid(message):
	"""Replaces <img embed="assets/frappe/images/filename.jpg" ...> with
	<img src="cid:content_id" ...> and return the modified message and
	a list of inline_images with {filename, filecontent, content_id}
	"""

	inline_images = []

	while True:
		matches = re.search("""embed=["'](.*?)["']""", message)
		if not matches:
			break
		groups = matches.groups()

		# found match
		img_path = groups[0]
		filename = img_path.rsplit("/")[-1]

		filecontent = get_filecontent_from_path(img_path)
		if not filecontent:
			message = re.sub("""embed=['"]{0}['"]""".format(img_path), "", message)
			continue

		content_id = random_string(10)

		inline_images.append(
			{"filename": filename, "filecontent": filecontent, "content_id": content_id}
		)

		message = re.sub(
			"""embed=['"]{0}['"]""".format(img_path), 'src="cid:{0}"'.format(content_id), message
		)

	return (message, inline_images)


def get_filecontent_from_path(path):
	if not path:
		return

	if path.startswith("/"):
		path = path[1:]

	if path.startswith("assets/"):
		# from public folder
		full_path = os.path.abspath(path)
	elif path.startswith("files/"):
		# public file
		full_path = frappe.get_site_path("public", path)
	elif path.startswith("private/files/"):
		# private file
		full_path = frappe.get_site_path(path)
	else:
		full_path = path

	if os.path.exists(full_path):
		with open(full_path, "rb") as f:
			filecontent = f.read()

		return filecontent
	else:
		return None


def get_header(header=None):
	"""Build header from template"""
	from frappe.utils.jinja import get_email_from_template

	if not header:
		return None

	if isinstance(header, string_types):
		# header = 'My Title'
		header = [header, None]
	if len(header) == 1:
		# header = ['My Title']
		header.append(None)
	# header = ['My Title', 'orange']
	title, indicator = header

	if not title:
		title = frappe.get_hooks("app_title")[-1]

	email_header, text = get_email_from_template(
		"email_header", {"header_title": title, "indicator": indicator}
	)

	return email_header


def sanitize_email_header(header: str):
	"""
	Removes all line boundaries in the headers.

	Email Policy (python's std) has some bugs in it which uses splitlines
	and raises ValueError (ref: https://github.com/python/cpython/blob/main/Lib/email/policy.py#L143).
	Hence removing all line boundaries while sanitization of headers to prevent such faliures.
	The line boundaries which are removed can be found here: https://docs.python.org/3/library/stdtypes.html#str.splitlines
	"""

	return "".join(header.splitlines())


def get_brand_logo(email_account):
	return email_account.get("brand_logo")
