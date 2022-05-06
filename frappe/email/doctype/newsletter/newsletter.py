# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See LICENSE

from __future__ import unicode_literals

from typing import Dict, List

import frappe
import frappe.utils
from frappe import _
from frappe.email.doctype.email_group.email_group import add_subscribers
from frappe.utils.verified_command import get_signed_params, verify_request
from frappe.website.website_generator import WebsiteGenerator

from .exceptions import NewsletterAlreadySentError, NewsletterNotSavedError, NoRecipientFoundError


class Newsletter(WebsiteGenerator):
	def onload(self):
		self.setup_newsletter_status()

	def validate(self):
		self.route = f"newsletters/{self.name}"
		self.validate_sender_address()
		self.validate_recipient_address()

	@property
	def newsletter_recipients(self) -> List[str]:
		if getattr(self, "_recipients", None) is None:
			self._recipients = self.get_recipients()
		return self._recipients

	@frappe.whitelist()
	def test_send(self):
		test_emails = frappe.utils.split_emails(self.test_email_id)
		self.queue_all(test_emails=test_emails)
		frappe.msgprint(_("Test email sent to {0}").format(self.test_email_id))

	@frappe.whitelist()
	def send_emails(self):
		"""send emails to leads and customers"""
		self.queue_all()
		frappe.msgprint(_("Email queued to {0} recipients").format(len(self.newsletter_recipients)))

	def setup_newsletter_status(self):
		"""Setup analytical status for current Newsletter. Can be accessible from desk."""
		if self.email_sent:
			status_count = frappe.get_all(
				"Email Queue",
				filters={"reference_doctype": self.doctype, "reference_name": self.name},
				fields=["status", "count(name)"],
				group_by="status",
				order_by="status",
				as_list=True,
			)
			self.get("__onload").status_count = dict(status_count)

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
		if self.send_from:
			frappe.utils.validate_email_address(self.send_from, throw=True)

	def validate_recipient_address(self):
		"""Validate if self.newsletter_recipients are all valid email addresses or not."""
		for recipient in self.newsletter_recipients:
			frappe.utils.validate_email_address(recipient, throw=True)

	def get_linked_email_queue(self) -> List[str]:
		"""Get list of email queue linked to this newsletter."""
		return frappe.get_all(
			"Email Queue",
			filters={
				"reference_doctype": self.doctype,
				"reference_name": self.name,
			},
			pluck="name",
		)

	def get_success_recipients(self) -> List[str]:
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

	def get_pending_recipients(self) -> List[str]:
		"""Get list of pending recipients of the newsletter. These
		recipients may not have receive the newsletter in the previous iteration.
		"""
		return [x for x in self.newsletter_recipients if x not in self.get_success_recipients()]

	def queue_all(self, test_emails: List[str] = None):
		"""Queue Newsletter to all the recipients generated from the `Email Group`
		table

		Args:
		        test_email (List[str], optional): Send test Newsletter to the passed set of emails.
		        Defaults to None.
		"""
		if test_emails:
			for test_email in test_emails:
				frappe.utils.validate_email_address(test_email, throw=True)
		else:
			self.validate()
			self.validate_send()

		newsletter_recipients = test_emails or self.get_pending_recipients()
		self.send_newsletter(emails=newsletter_recipients)

		if not test_emails:
			self.email_sent = True
			self.schedule_send = frappe.utils.now_datetime()
			self.scheduled_to_send = len(newsletter_recipients)
			self.save()

	def get_newsletter_attachments(self) -> List[Dict[str, str]]:
		"""Get list of attachments on current Newsletter"""
		attachments = []

		if self.send_attachments:
			files = frappe.get_all(
				"File",
				filters={"attached_to_doctype": "Newsletter", "attached_to_name": self.name},
				order_by="creation desc",
				pluck="name",
			)
			attachments.extend({"fid": file} for file in files)

		return attachments

	def send_newsletter(self, emails: List[str]):
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
		if self.content_type == "HTML":
			return frappe.render_template(self.message_html, {"doc": self.as_dict()})
		if self.content_type == "Markdown":
			return frappe.utils.markdown(self.message_md)
		# fallback to Rich Text
		return self.message

	def get_recipients(self) -> List[str]:
		"""Get recipients from Email Group"""
		emails = frappe.get_all(
			"Email Group Member",
			filters={"unsubscribed": 0, "email_group": ("in", self.get_email_groups())},
			pluck="email",
		)
		return list(set(emails))

	def get_email_groups(self) -> List[str]:
		# wondering why the 'or'? i can't figure out why both aren't equivalent - @gavin
		return [x.email_group for x in self.email_group] or frappe.get_all(
			"Newsletter Email Group",
			filters={"parent": self.name, "parenttype": "Newsletter"},
			pluck="email_group",
		)

	def get_attachments(self) -> List[Dict[str, str]]:
		return frappe.get_all(
			"File",
			fields=["name", "file_name", "file_url", "is_private"],
			filters={
				"attached_to_name": self.name,
				"attached_to_doctype": "Newsletter",
				"is_private": 0,
			},
		)

	def get_context(self, context):
		newsletters = get_newsletter_list("Newsletter", None, None, 0)
		if newsletters:
			newsletter_list = [d.name for d in newsletters]
			if self.name not in newsletter_list:
				frappe.redirect_to_message(
					_("Permission Error"), _("You are not permitted to view the newsletter.")
				)
				frappe.local.flags.redirect_location = frappe.local.response.location
				raise frappe.Redirect
			else:
				context.attachments = self.get_attachments()
		context.no_cache = 1
		context.show_sidebar = True


@frappe.whitelist(allow_guest=True)
def confirmed_unsubscribe(email, group):
	"""unsubscribe the email(user) from the mailing list(email_group)"""
	frappe.flags.ignore_permissions = True
	doc = frappe.get_doc("Email Group Member", {"email": email, "email_group": group})
	if not doc.unsubscribed:
		doc.unsubscribed = 1
		doc.save(ignore_permissions=True)


@frappe.whitelist(allow_guest=True)
def subscribe(email, email_group=_("Website")):
	"""API endpoint to subscribe an email to a particular email group. Triggers a confirmation email."""

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
			<p>{0}. {1}.</p>
			<p><a href="{2}">{3}</a></p>
		""".format(
			*translatable_content
		)

	frappe.sendmail(
		email,
		subject=email_subject,
		content=content,
		now=True,
	)


@frappe.whitelist(allow_guest=True)
def confirm_subscription(email, email_group=_("Website")):
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
			"show_sidebar": True,
			"show_search": True,
			"no_breadcrumbs": True,
			"title": _("Newsletter"),
			"get_list": get_newsletter_list,
			"row_template": "email/doctype/newsletter/templates/newsletter_row.html",
		}
	)


def get_newsletter_list(
	doctype, txt, filters, limit_start, limit_page_length=20, order_by="modified"
):
	email_group_list = frappe.db.sql(
		"""SELECT eg.name
		FROM `tabEmail Group` eg, `tabEmail Group Member` egm
		WHERE egm.unsubscribed=0
		AND eg.name=egm.email_group
		AND egm.email = %s""",
		frappe.session.user,
	)
	email_group_list = [d[0] for d in email_group_list]

	if email_group_list:
		return frappe.db.sql(
			"""SELECT n.name, n.subject, n.message, n.modified
			FROM `tabNewsletter` n, `tabNewsletter Email Group` neg
			WHERE n.name = neg.parent
			AND n.email_sent=1
			AND n.published=1
			AND neg.email_group in ({0})
			ORDER BY n.modified DESC LIMIT {1} OFFSET {2}
			""".format(
				",".join(["%s"] * len(email_group_list)), limit_page_length, limit_start
			),
			email_group_list,
			as_dict=1,
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

	for newsletter in scheduled_newsletter:
		try:
			frappe.get_doc("Newsletter", newsletter).queue_all()

		except Exception:
			frappe.db.rollback()

			# wasn't able to send emails :(
			frappe.db.set_value("Newsletter", newsletter, "email_sent", 0)
			message = (
				f"Newsletter {newsletter} failed to send" "\n\n" f"Traceback: {frappe.get_traceback()}"
			)
			frappe.log_error(title="Send Newsletter", message=message)

		if not frappe.flags.in_test:
			frappe.db.commit()
