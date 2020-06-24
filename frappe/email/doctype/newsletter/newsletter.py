# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals

import frappe
import frappe.utils
from frappe import throw, _
from frappe.website.website_generator import WebsiteGenerator
from frappe.utils.verified_command import get_signed_params, verify_request
from frappe.utils.background_jobs import enqueue
from frappe.email.queue import send
from frappe.email.doctype.email_group.email_group import add_subscribers
from frappe.utils import parse_addr, now_datetime
from frappe.utils import validate_email_address


class Newsletter(WebsiteGenerator):
	def onload(self):
		if self.email_sent:
			self.get("__onload").status_count = dict(frappe.db.sql("""select status, count(name)
				from `tabEmail Queue` where reference_doctype=%s and reference_name=%s
				group by status""", (self.doctype, self.name))) or None

	def validate(self):
		self.route = "newsletters/" + self.name
		if self.send_from:
			validate_email_address(self.send_from, True)

	def test_send(self, doctype="Lead"):
		self.recipients = frappe.utils.split_emails(self.test_email_id)
		self.queue_all()
		frappe.msgprint(_("Scheduled to send to {0}").format(self.test_email_id))

	def send_emails(self):
		"""send emails to leads and customers"""
		if self.email_sent:
			throw(_("Newsletter has already been sent"))

		self.recipients = self.get_recipients()

		if self.recipients:
			if getattr(frappe.local, "is_ajax", False):
				self.validate_send()
				# using default queue with a longer timeout as this isn't a scheduled task
				enqueue(send_newsletter, queue='default', timeout=6000, event='send_newsletter',
					newsletter=self.name)

			else:
				self.queue_all()

			frappe.msgprint(_("Scheduled to send to {0} recipients").format(len(self.recipients)))

		else:
			frappe.msgprint(_("Newsletter should have atleast one recipient"))

	def queue_all(self):
		if not self.get("recipients"):
			# in case it is called via worker
			self.recipients = self.get_recipients()

		self.validate_send()

		sender = self.send_from or frappe.utils.get_formatted_email(self.owner)

		if not frappe.flags.in_test:
			frappe.db.auto_commit_on_many_writes = True

		attachments = []
		if self.send_attachments:
			files = frappe.get_all("File", fields=["name"], filters={"attached_to_doctype": "Newsletter",
				"attached_to_name": self.name}, order_by="creation desc")

			for file in files:
				try:
					# these attachments will be attached on-demand
					# and won't be stored in the message
					attachments.append({"fid": file.name})
				except IOError:
					frappe.throw(_("Unable to find attachment {0}").format(file.name))

		send(recipients=self.recipients, sender=sender,
			subject=self.subject, message=self.message,
			reference_doctype=self.doctype, reference_name=self.name,
			add_unsubscribe_link=self.send_unsubscribe_link, attachments=attachments,
			unsubscribe_method="/unsubscribe",
			unsubscribe_params={"name": self.name},
			send_priority=0, queue_separately=True)

		if not frappe.flags.in_test:
			frappe.db.auto_commit_on_many_writes = False

		self.db_set("email_sent", 1)
		self.db_set("schedule_send", now_datetime())
		self.db_set("scheduled_to_send", len(self.recipients))

	def get_recipients(self):
		"""Get recipients from Email Group"""
		recipients_list = []
		for email_group in get_email_groups(self.name):
			for d in frappe.db.get_all("Email Group Member", ["email"],
				{"unsubscribed": 0, "email_group": email_group.email_group}):
					recipients_list.append(d.email)
		return list(set(recipients_list))

	def validate_send(self):
		if self.get("__islocal"):
			throw(_("Please save the Newsletter before sending"))

	def get_context(self, context):
		newsletters = get_newsletter_list("Newsletter", None, None, 0)
		if newsletters:
			newsletter_list = [d.name for d in newsletters]
			if self.name not in newsletter_list:
				frappe.redirect_to_message(_('Permission Error'),
					_("You are not permitted to view the newsletter."))
				frappe.local.flags.redirect_location = frappe.local.response.location
				raise frappe.Redirect
			else:
				context.attachments = get_attachments(self.name)
		context.no_cache = 1
		context.show_sidebar = True


def get_attachments(name):
	return frappe.get_all("File",
			fields=["name", "file_name", "file_url", "is_private"],
			filters = {"attached_to_name": name, "attached_to_doctype": "Newsletter", "is_private":0})


def get_email_groups(name):
	return frappe.db.get_all("Newsletter Email Group", ["email_group"],{"parent":name, "parenttype":"Newsletter"})


@frappe.whitelist(allow_guest=True)
def confirmed_unsubscribe(email, group):
	""" unsubscribe the email(user) from the mailing list(email_group) """
	frappe.flags.ignore_permissions=True
	doc = frappe.get_doc("Email Group Member", {"email": email, "email_group": group})
	if not doc.unsubscribed:
		doc.unsubscribed = 1
		doc.save(ignore_permissions = True)

def create_lead(email_id):
	"""create a lead if it does not exist"""
	from frappe.model.naming import get_default_naming_series
	full_name, email_id = parse_addr(email_id)
	if frappe.db.get_value("Lead", {"email_id": email_id}):
		return

	lead = frappe.get_doc({
		"doctype": "Lead",
		"email_id": email_id,
		"lead_name": full_name or email_id,
		"status": "Lead",
		"naming_series": get_default_naming_series("Lead"),
		"company": frappe.db.get_default("Company"),
		"source": "Email"
	})
	lead.insert()


@frappe.whitelist(allow_guest=True)
def subscribe(email, email_group=_('Website')):
	url = frappe.utils.get_url("/api/method/frappe.email.doctype.newsletter.newsletter.confirm_subscription") +\
		"?" + get_signed_params({"email": email, "email_group": email_group})

	email_template = frappe.db.get_value('Email Group', email_group, ['confirmation_email_template'])

	content=''
	if email_template:
		args = dict(
			email=email,
			confirmation_url=url,
			email_group=email_group
		)

		email_template = frappe.get_doc("Email Template", email_template)
		content = frappe.render_template(email_template.response, args)

	if not content:
		messages = (
			_("Thank you for your interest in subscribing to our updates"),
			_("Please verify your Email Address"),
			url,
			_("Click here to verify")
		)

		content = """
		<p>{0}. {1}.</p>
		<p><a href="{2}">{3}</a></p>
		""".format(*messages)

	frappe.sendmail(email, subject=getattr('email_template', 'subject', '') or _("Confirm Your Email"), content=content, now=True)

@frappe.whitelist(allow_guest=True)
def confirm_subscription(email, email_group=_('Website')):
	if not verify_request():
		return

	if not frappe.db.exists("Email Group", email_group):
		frappe.get_doc({
			"doctype": "Email Group",
			"title": email_group
		}).insert(ignore_permissions=True)

	frappe.flags.ignore_permissions = True

	add_subscribers(email_group, email)
	frappe.db.commit()

	frappe.respond_as_web_page(_("Confirmed"),
		_("{0} has been successfully added to the Email Group.").format(email),
		indicator_color='green')


def send_newsletter(newsletter):
	try:
		doc = frappe.get_doc("Newsletter", newsletter)
		doc.queue_all()

	except:
		frappe.db.rollback()

		# wasn't able to send emails :(
		doc.db_set("email_sent", 0)
		frappe.db.commit()

		frappe.log_error(title='Send Newsletter')

		raise

	else:
		frappe.db.commit()


def get_list_context(context=None):
	context.update({
		"show_sidebar": True,
		"show_search": True,
		'no_breadcrumbs': True,
		"title": _("Newsletter"),
		"get_list": get_newsletter_list,
		"row_template": "email/doctype/newsletter/templates/newsletter_row.html",
	})


def get_newsletter_list(doctype, txt, filters, limit_start, limit_page_length=20, order_by="modified"):
	email_group_list = frappe.db.sql('''SELECT eg.name
		FROM `tabEmail Group` eg, `tabEmail Group Member` egm
		WHERE egm.unsubscribed=0
		AND eg.name=egm.email_group
		AND egm.email = %s''', frappe.session.user)
	email_group_list = [d[0] for d in email_group_list]

	if email_group_list:
		return frappe.db.sql('''SELECT n.name, n.subject, n.message, n.modified
			FROM `tabNewsletter` n, `tabNewsletter Email Group` neg
			WHERE n.name = neg.parent
			AND n.email_sent=1
			AND n.published=1
			AND neg.email_group in ({0})
			ORDER BY n.modified DESC LIMIT {1} OFFSET {2}
			'''.format(','.join(['%s'] * len(email_group_list)),
					limit_page_length, limit_start), email_group_list, as_dict=1)

def send_scheduled_email():
	"""Send scheduled newsletter to the recipients."""
	scheduled_newsletter = frappe.get_all('Newsletter', filters = {
		'schedule_send': ('<=', now_datetime()),
		'email_sent': 0
	}, fields = ['name'], ignore_ifnull=True)
	for newsletter in scheduled_newsletter:
		send_newsletter(newsletter.name)
