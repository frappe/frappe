# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See LICENSE


import frappe
import frappe.utils
from frappe import _
from frappe.email.doctype.email_group.email_group import add_subscribers
from frappe.rate_limiter import rate_limit
from frappe.utils.safe_exec import is_job_queued
from frappe.utils.verified_command import get_signed_params, verify_request
from frappe.website.website_generator import WebsiteGenerator

from .exceptions import NewsletterAlreadySentError, NewsletterNotSavedError, NoRecipientFoundError


class Newsletter(WebsiteGenerator):
	def validate(self):
		self.route = f"newsletters/{self.name}"
		self.validate_sender_address()
		self.validate_recipient_address()
		self.validate_publishing()

	@property
	def newsletter_recipients(self) -> list[str]:
		if getattr(self, "_recipients", None) is None:
			self._recipients = self.get_recipients()
		return self._recipients

	@frappe.whitelist()
	def get_sending_status(self):
		count_by_status = frappe.get_all(
			"Email Queue",
			filters={"reference_doctype": self.doctype, "reference_name": self.name},
			fields=["status", "count(name) as count"],
			group_by="status",
			order_by="status",
		)
		sent = 0
		error = 0
		total = 0
		for row in count_by_status:
			if row.status == "Sent":
				sent = row.count
			elif row.status == "Error":
				error = row.count
			total += row.count
		emails_queued = is_job_queued(
			job_name=frappe.utils.get_job_name("send_bulk_emails_for", self.doctype, self.name),
			queue="long",
		)
		return {"sent": sent, "error": error, "total": total, "emails_queued": emails_queued}

	@frappe.whitelist()
	def send_test_email(self, email):
		test_emails = frappe.utils.validate_email_address(email, throw=True)
		self.send_newsletter(emails=test_emails)
		frappe.msgprint(_("Test email sent to {0}").format(email), alert=True)

	@frappe.whitelist()
	def find_broken_links(self):
		import requests
		from bs4 import BeautifulSoup

		html = self.get_message()
		soup = BeautifulSoup(html, "html.parser")
		links = soup.find_all("a")
		images = soup.find_all("img")
		broken_links = []
		for el in links + images:
			url = el.attrs.get("href") or el.attrs.get("src")
			try:
				response = requests.head(url, verify=False, timeout=5)
				if response.status_code >= 400:
					broken_links.append(url)
			except Exception:
				broken_links.append(url)
		return broken_links

	@frappe.whitelist()
	def send_emails(self):
		"""queue sending emails to recipients"""
		self.schedule_sending = False
		self.schedule_send = None
		self.queue_all()

	def validate_send(self):
		"""Validate if Newsletter can be sent."""
		self.validate_newsletter_status()
		self.validate_newsletter_recipients()

	def validate_newsletter_status(self):
		if self.email_sent:
			frappe.throw(_("Newsletter has already been sent"), exc=NewsletterAlreadySentError)

		if self.get("__islocal"):
			frappe.throw(_("Please save the Newsletter before sending"), exc=NewsletterNotSavedError)

	def validate_newsletter_recipients(self):
		if not self.newsletter_recipients:
			frappe.throw(_("Newsletter should have atleast one recipient"), exc=NoRecipientFoundError)
		self.validate_recipient_address()

	def validate_sender_address(self):
		"""Validate self.send_from is a valid email address or not."""
		if self.sender_email:
			frappe.utils.validate_email_address(self.sender_email, throw=True)
			self.send_from = (
				f"{self.sender_name} <{self.sender_email}>" if self.sender_name else self.sender_email
			)

	def validate_recipient_address(self):
		"""Validate if self.newsletter_recipients are all valid email addresses or not."""
		for recipient in self.newsletter_recipients:
			frappe.utils.validate_email_address(recipient, throw=True)

	def validate_publishing(self):
		if self.send_webview_link and not self.published:
			frappe.throw(_("Newsletter must be published to send webview link in email"))

	def get_linked_email_queue(self) -> list[str]:
		"""Get list of email queue linked to this newsletter."""
		return frappe.get_all(
			"Email Queue",
			filters={
				"reference_doctype": self.doctype,
				"reference_name": self.name,
			},
			pluck="name",
		)

	def get_success_recipients(self) -> list[str]:
		"""Recipients who have already received the newsletter.

		Couldn't think of a better name ;)
		"""
		return frappe.get_all(
			"Email Queue Recipient",
			filters={
				"status": ("in", ["Not Sent", "Sending", "Sent"]),
				"parent": ("in", self.get_linked_email_queue()),
			},
			pluck="recipient",
		)

	def get_pending_recipients(self) -> list[str]:
		"""Get list of pending recipients of the newsletter. These
		recipients may not have receive the newsletter in the previous iteration.
		"""
		success_recipients = set(self.get_success_recipients())
		return [x for x in self.newsletter_recipients if x not in success_recipients]

	def queue_all(self):
		"""Queue Newsletter to all the recipients generated from the `Email Group` table"""
		self.validate()
		self.validate_send()

		recipients = self.get_pending_recipients()
		self.send_newsletter(emails=recipients)

		self.email_sent = True
		self.email_sent_at = frappe.utils.now()
		self.total_recipients = len(recipients)
		self.save()

	def get_newsletter_attachments(self) -> list[dict[str, str]]:
		"""Get list of attachments on current Newsletter"""
		return [{"file_url": row.attachment} for row in self.attachments]

	def send_newsletter(self, emails: list[str]):
		"""Trigger email generation for `emails` and add it in Email Queue."""
		attachments = self.get_newsletter_attachments()
		sender = self.send_from or frappe.utils.get_formatted_email(self.owner)
		args = self.as_dict()
		args["message"] = self.get_message()

		is_auto_commit_set = bool(frappe.db.auto_commit_on_many_writes)
		frappe.db.auto_commit_on_many_writes = not frappe.flags.in_test

		frappe.sendmail(
			subject=self.subject,
			sender=sender,
			recipients=emails,
			attachments=attachments,
			template="newsletter",
			add_unsubscribe_link=self.send_unsubscribe_link,
			unsubscribe_method="/unsubscribe",
			unsubscribe_params={"name": self.name},
			reference_doctype=self.doctype,
			reference_name=self.name,
			queue_separately=True,
			send_priority=0,
			args=args,
		)

		frappe.db.auto_commit_on_many_writes = is_auto_commit_set

	def get_message(self) -> str:
		message = self.message
		if self.content_type == "Markdown":
			message = frappe.utils.md_to_html(self.message_md)
		if self.content_type == "HTML":
			message = self.message_html

		return frappe.render_template(message, {"doc": self.as_dict()})

	def get_recipients(self) -> list[str]:
		"""Get recipients from Email Group"""
		emails = frappe.get_all(
			"Email Group Member",
			filters={"unsubscribed": 0, "email_group": ("in", self.get_email_groups())},
			pluck="email",
		)
		return list(set(emails))

	def get_email_groups(self) -> list[str]:
		# wondering why the 'or'? i can't figure out why both aren't equivalent - @gavin
		return [x.email_group for x in self.email_group] or frappe.get_all(
			"Newsletter Email Group",
			filters={"parent": self.name, "parenttype": "Newsletter"},
			pluck="email_group",
		)

	def get_attachments(self) -> list[dict[str, str]]:
		return frappe.get_all(
			"File",
			fields=["name", "file_name", "file_url", "is_private"],
			filters={
				"attached_to_name": self.name,
				"attached_to_doctype": "Newsletter",
				"is_private": 0,
			},
		)


def confirmed_unsubscribe(email, group):
	"""unsubscribe the email(user) from the mailing list(email_group)"""
	frappe.flags.ignore_permissions = True
	doc = frappe.get_doc("Email Group Member", {"email": email, "email_group": group})
	if not doc.unsubscribed:
		doc.unsubscribed = 1
		doc.save(ignore_permissions=True)


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=10, seconds=60 * 60)
def subscribe(email, email_group=None):  # noqa
	"""API endpoint to subscribe an email to a particular email group. Triggers a confirmation email."""

	if email_group is None:
		email_group = _("Website")

	# build subscription confirmation URL
	api_endpoint = frappe.utils.get_url(
		"/api/method/frappe.email.doctype.newsletter.newsletter.confirm_subscription"
	)
	signed_params = get_signed_params({"email": email, "email_group": email_group})
	confirm_subscription_url = f"{api_endpoint}?{signed_params}"

	# fetch custom template if available
	email_confirmation_template = frappe.db.get_value(
		"Email Group", email_group, "confirmation_email_template"
	)

	# build email and send
	if email_confirmation_template:
		args = {"email": email, "confirmation_url": confirm_subscription_url, "email_group": email_group}
		email_template = frappe.get_doc("Email Template", email_confirmation_template)
		email_subject = email_template.subject
		content = frappe.render_template(email_template.response, args)
	else:
		email_subject = _("Confirm Your Email")
		translatable_content = (
			_("Thank you for your interest in subscribing to our updates"),
			_("Please verify your Email Address"),
			confirm_subscription_url,
			_("Click here to verify"),
		)
		content = """
			<p>{}. {}.</p>
			<p><a href="{}">{}</a></p>
		""".format(
			*translatable_content
		)

	frappe.sendmail(
		email,
		subject=email_subject,
		content=content,
	)


@frappe.whitelist(allow_guest=True)
def confirm_subscription(email, email_group=_("Website")):  # noqa
	"""API endpoint to confirm email subscription.
	This endpoint is called when user clicks on the link sent to their mail.
	"""
	if not verify_request():
		return

	if not frappe.db.exists("Email Group", email_group):
		frappe.get_doc({"doctype": "Email Group", "title": email_group}).insert(ignore_permissions=True)

	frappe.flags.ignore_permissions = True

	add_subscribers(email_group, email)
	frappe.db.commit()

	frappe.respond_as_web_page(
		_("Confirmed"),
		_("{0} has been successfully added to the Email Group.").format(email),
		indicator_color="green",
	)


def get_list_context(context=None):
	context.update(
		{
			"show_search": True,
			"no_breadcrumbs": True,
			"title": _("Newsletters"),
			"filters": {"published": 1},
			"row_template": "email/doctype/newsletter/templates/newsletter_row.html",
		}
	)


def send_scheduled_email():
	"""Send scheduled newsletter to the recipients."""
	scheduled_newsletter = frappe.get_all(
		"Newsletter",
		filters={
			"schedule_send": ("<=", frappe.utils.now_datetime()),
			"email_sent": False,
			"schedule_sending": True,
		},
		ignore_ifnull=True,
		pluck="name",
	)

	for newsletter_name in scheduled_newsletter:
		try:
			newsletter = frappe.get_doc("Newsletter", newsletter_name)
			newsletter.queue_all()

		except Exception:
			frappe.db.rollback()

			# wasn't able to send emails :(
			frappe.db.set_value("Newsletter", newsletter_name, "email_sent", 0)
			newsletter.log_error("Failed to send newsletter")

		if not frappe.flags.in_test:
			frappe.db.commit()
