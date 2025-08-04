# Copyright (c) 2018, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
import os
from collections import namedtuple
from functools import partial

import frappe
from frappe import _
from frappe.core.doctype.role.role import get_info_based_on_role, get_user_info
from frappe.core.doctype.sms_settings.sms_settings import send_sms
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from frappe.integrations.doctype.slack_webhook_url.slack_webhook_url import send_slack_message
from frappe.model.document import Document
from frappe.modules.utils import export_module_json, get_doc_module
from frappe.utils import add_to_date, cast, now_datetime, nowdate, validate_email_address
from frappe.utils.data import evaluate_filters
from frappe.utils.jinja import validate_template
from frappe.utils.safe_exec import get_safe_globals

FORMATS = {"HTML": ".html", "Markdown": ".md", "Plain Text": ".txt"}
FORBIDDEN_DOCUMENT_TYPES = frozenset(("Email Queue",))
DATE_BASED_EVENTS = frozenset(("Days Before", "Days After"))


class Notification(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.email.doctype.notification_recipient.notification_recipient import NotificationRecipient
		from frappe.types import DF

		attach_print: DF.Check
		channel: DF.Literal["Email", "Slack", "System Notification", "SMS"]
		condition: DF.Code | None
		condition_type: DF.Literal["Python", "Filters"]
		date_changed: DF.Literal[None]
		datetime_changed: DF.Literal[None]
		datetime_last_run: DF.Datetime | None
		days_in_advance: DF.Int
		document_type: DF.Link
		enabled: DF.Check
		event: DF.Literal[
			"",
			"New",
			"Save",
			"Submit",
			"Cancel",
			"Days After",
			"Days Before",
			"Minutes After",
			"Minutes Before",
			"Value Change",
			"Method",
			"Custom",
		]
		filters: DF.Code | None
		is_standard: DF.Check
		message: DF.Code | None
		message_type: DF.Literal["Markdown", "HTML", "Plain Text"]
		method: DF.Data | None
		minutes_offset: DF.Int
		module: DF.Link | None
		print_format: DF.Link | None
		property_value: DF.Data | None
		recipients: DF.Table[NotificationRecipient]
		send_system_notification: DF.Check
		send_to_all_assignees: DF.Check
		sender: DF.Link | None
		sender_email: DF.Data | None
		set_property_after_alert: DF.Literal[None]
		slack_webhook_url: DF.Link | None
		subject: DF.Data | None
		value_changed: DF.Literal[None]
	# end: auto-generated types

	def onload(self):
		"""load message"""
		if self.is_standard:
			self.message = self.get_template()

	def autoname(self):
		if not self.name:
			self.name = self.subject

	# START: PreviewRenderer API

	@frappe.whitelist()
	def preview_meets_condition(self, preview_document):
		if not self.condition and not self.filters:
			return _("Yes")
		try:
			doc = frappe.get_cached_doc(self.document_type, preview_document)
			if self.condition_type == "Python":
				context = get_context(doc)
				return _("Yes") if frappe.safe_eval(self.condition, eval_locals=context) else _("No")
			elif self.condition_type == "Filters":
				return _("Yes") if evaluate_filters(doc, json.loads(self.filters)) else _("No")
		except Exception as e:
			frappe.local.message_log = []
			return _("Failed to evaluate conditions: {}").format(e)

	@frappe.whitelist()
	def preview_message(self, preview_document):
		try:
			doc = frappe.get_cached_doc(self.document_type, preview_document)
			context = get_context(doc)
			context.update({"alert": self, "comments": None})
			if doc.get("_comments"):
				context["comments"] = json.loads(doc.get("_comments"))
			if self.is_standard:
				self.load_standard_properties(context)
			msg = frappe.render_template(self.message, context)
			if self.channel == "SMS":
				return frappe.utils.strip_html_tags(msg)
			return msg
		except Exception as e:
			return _("Failed to render message: {}").format(e)

	@frappe.whitelist()
	def preview_subject(self, preview_document):
		try:
			doc = frappe.get_cached_doc(self.document_type, preview_document)
			context = get_context(doc)
			context.update({"alert": self, "comments": None})
			if doc.get("_comments"):
				context["comments"] = json.loads(doc.get("_comments"))
			if self.is_standard:
				self.load_standard_properties(context)
			if not self.subject:
				return _("No subject")
			if "{" in self.subject:
				return frappe.render_template(self.subject, context)
			return self.subject
		except Exception as e:
			return _("Failed to render subject: {}").format(e)

	# END: PreviewRenderer API

	def before_save(self):
		self.remove_invalid_condition()

	def validate(self):
		if self.channel in ("Email", "Slack", "System Notification"):
			validate_template(self.subject)

		validate_template(self.message)

		if self.event in ("Days Before", "Days After") and not self.date_changed:
			frappe.throw(_("Please specify which date field must be checked"))

		if self.event in ("Minutes Before", "Minutes After"):
			if not self.datetime_changed:
				frappe.throw(_("Please specify which datetime field must be checked"))
			if not self.minutes_offset:
				frappe.throw(_("Please specify the minutes offset"))
			if self.minutes_offset < 10:
				frappe.throw(
					_("Please specify at least 10 minutes due to the trigger cadence of the scheduler")
				)

		if self.event == "Value Change" and not self.value_changed:
			frappe.throw(_("Please specify which value field must be checked"))

		self.validate_forbidden_document_types()
		self.validate_condition()
		self.validate_filters()
		self.validate_standard()
		clear_notification_cache()

	def clear_cache(self):
		super().clear_cache()
		clear_notification_cache()

	def on_update(self):
		path = export_module_json(self, self.is_standard, self.module)
		if path and self.message:
			extension = FORMATS.get(self.message_type, ".md")
			file_path = path + extension
			with open(file_path, "w") as f:
				f.write(self.message)

			# py
			if not os.path.exists(path + ".py"):
				with open(path + ".py", "w") as f:
					f.write(
						"""import frappe

def get_context(context):
	# do your magic here
	pass
"""
					)

	def validate_standard(self):
		if self.is_standard and self.enabled and not frappe.conf.developer_mode:
			frappe.throw(
				_("Cannot edit Standard Notification. To edit, please disable this and duplicate it")
			)

	def remove_invalid_condition(self):
		if self.condition_type == "Filters":
			self.condition = None
		elif self.condition_type == "Python":
			self.filters = None

	def validate_condition(self):
		if not self.condition:
			return

		temp_doc = frappe.new_doc(self.document_type)
		try:
			frappe.safe_eval(self.condition, None, get_context(temp_doc.as_dict()))
		except Exception:
			frappe.throw(_("The Condition '{0}' is invalid").format(self.condition))

	def validate_filters(self):
		if not self.filters:
			return

		filters = json.loads(self.filters)
		dummy_doc = frappe.new_doc(self.document_type)
		evaluate_filters(dummy_doc, filters)

	def validate_forbidden_document_types(self):
		if self.document_type in FORBIDDEN_DOCUMENT_TYPES or (
			frappe.get_meta(self.document_type).istable and self.event not in DATE_BASED_EVENTS
		):
			# only date based events are allowed for child tables
			frappe.throw(
				_("Cannot set Notification with event {0} on Document Type {1}").format(
					_(self.event), _(self.document_type)
				)
			)

	def get_documents_for_today(self):
		"""get list of documents that will be triggered today"""
		docs = []

		diff_days = self.days_in_advance
		if self.event == "Days After":
			diff_days = -diff_days

		reference_date = add_to_date(nowdate(), days=diff_days)
		reference_date_start = reference_date + " 00:00:00.000000"
		reference_date_end = reference_date + " 23:59:59.000000"

		doc_list = frappe.get_all(
			self.document_type,
			fields="name",
			filters=[
				{self.date_changed: (">=", reference_date_start)},
				{self.date_changed: ("<=", reference_date_end)},
			],
		)

		filters = json.loads(self.filters) if self.condition_type == "Filters" and self.filters else None

		for d in doc_list:
			doc = frappe.get_lazy_doc(self.document_type, d.name)

			if (
				self.condition_type == "Python"
				and self.condition
				and not frappe.safe_eval(self.condition, None, get_context(doc))
			):
				continue
			elif filters and not evaluate_filters(doc, filters):
				continue

			docs.append(doc)

		return docs

	def get_documents_for_this_moment(self) -> list[Document]:
		"""
		Get list of documents that will be triggered at this moment.

		This method retrieves documents based on the specified datetime field and minutes offset.
		It considers documents that fall within the time range from the last run time plus the offset
		up to the current time plus the offset.

		Returns:
		        list: A list of document objects that meet the criteria for notification.
		"""
		docs = []

		offset_in_minutes = self.minutes_offset

		now = now_datetime()  # reference now
		last = (
			# one ficticious scheduler tick earlier if frist run
			add_to_date(now, minutes=-5) if not self.datetime_last_run else self.datetime_last_run
		)

		if self.event == "Minutes After":
			offset = partial(add_to_date, minutes=-offset_in_minutes)
		else:
			offset = partial(add_to_date, minutes=offset_in_minutes)

		(lower, upper) = map(offset, [last, now])  # nosemgrep

		doc_list = frappe.get_all(
			self.document_type,
			fields="name",
			filters=[
				{self.datetime_changed: (">", lower)},
				{self.datetime_changed: ("<=", upper)},
			],
		)

		self.db_set("datetime_last_run", now)  # set reference now for next run

		filters = json.loads(self.filters) if self.condition_type == "Filters" and self.filters else None

		for d in doc_list:
			doc = frappe.get_lazy_doc(self.document_type, d.name)

			if (
				self.condition_type == "Python"
				and self.condition
				and not frappe.safe_eval(self.condition, None, get_context(doc))
			):
				continue
			elif filters and not evaluate_filters(doc, filters):
				continue

			docs.append(doc)

		return docs

	def queue_send(self, doc, enqueue_after_commit=True):
		"""
		Enqueue the process to build recipients and send notifications.

		This method is particularly useful for sending notifications, especially 'Custom'-type,
		without the additional overhead associated with `Document.queue_action`.

		Args:
		              doc (Document): The document object for which the notification is being sent.
		              enqueue_after_commit (bool, optional): If True, the task will be enqueued after
		                the current transaction is committed. Defaults to True.

		Note:
		              This method is the recommended way to send 'Custom'-type notifications.

		Example:
		              To queue a notification from a server script:

		              ```python
		              notification = frappe.get_doc("Notification", "My Notification", ignore_permissions=True)
		              notification.queue_send(customer)
		              ```

		              This example queues the "My Notification" to be sent for the specified customer document.
		"""
		from frappe.utils.background_jobs import enqueue

		return enqueue(
			"frappe.email.doctype.notification.notification.evaluate_alert",
			doc=doc,
			alert=self,
			now=frappe.in_test,
			enqueue_after_commit=enqueue_after_commit,
		)

	def send(self, doc):
		"""Build recipients and send Notification"""

		context = get_context(doc)
		context.update({"alert": self, "comments": None})
		if doc.get("_comments"):
			context["comments"] = json.loads(doc.get("_comments"))

		if self.is_standard:
			self.load_standard_properties(context)

		self.send_notification_by_channel(doc, context)

		if self.set_property_after_alert:
			allow_update = True
			if (
				doc.docstatus.is_submitted()
				and not doc.meta.get_field(self.set_property_after_alert).allow_on_submit
			):
				allow_update = False
			try:
				if allow_update and not doc.flags.in_notification_update:
					fieldname = self.set_property_after_alert
					value = self.property_value
					if doc.meta.get_field(fieldname).fieldtype in frappe.model.numeric_fieldtypes:
						value = frappe.utils.cint(value)

					doc.reload()
					doc.set(fieldname, value)
					doc.flags.updater_reference = {
						"doctype": self.doctype,
						"docname": self.name,
						"label": _("via Notification"),
					}
					doc.flags.in_notification_update = True
					doc.save(ignore_permissions=True)
					doc.flags.in_notification_update = False
			except Exception:
				self.log_error("Document update failed")

	def send_notification_by_channel(self, doc, context):
		"""Send notification based on the specified channel."""
		try:
			if self.channel == "Email":
				self.send_an_email(doc, context)
			elif self.channel == "Slack":
				self.send_a_slack_msg(doc, context)
			elif self.channel == "SMS":
				self.send_sms(doc, context)
			elif self.channel == "System Notification" or self.send_system_notification:
				self.create_system_notification(doc, context)
		except Exception:
			self.log_error("Failed to send Notification")

	def create_system_notification(self, doc, context):
		subject = self.subject
		if "{" in subject:
			subject = frappe.render_template(self.subject, context)

		attachments = self.get_attachment(doc)

		recipients, cc, bcc = self.get_list_of_recipients(doc, context)

		users = recipients + cc + bcc

		if not users:
			return

		notification_doc = {
			"type": "Alert",
			"document_type": get_reference_doctype(doc),
			"document_name": get_reference_name(doc),
			"subject": subject,
			"from_user": doc.modified_by or doc.owner,
			"email_content": frappe.render_template(self.message, context),
			"attached_file": attachments and json.dumps(attachments[0]),
		}
		enqueue_create_notification(users, notification_doc)

	def send_an_email(self, doc, context):
		from email.utils import formataddr

		from frappe.core.doctype.communication.email import _make as make_communication

		subject = self.subject
		if "{" in subject:
			subject = frappe.render_template(self.subject, context)

		attachments = self.get_attachment(doc)
		recipients, cc, bcc = self.get_list_of_recipients(doc, context)
		if not (recipients or cc or bcc):
			return

		sender = None
		message = frappe.render_template(self.message, context)
		if self.sender and self.sender_email:
			sender = formataddr((self.sender, self.sender_email))

		communication = None
		# Add mail notification to communication list
		# No need to add if it is already a communication.
		if doc.doctype != "Communication":
			communication = make_communication(
				doctype=get_reference_doctype(doc),
				name=get_reference_name(doc),
				content=message,
				subject=subject,
				sender=sender,
				recipients=recipients,
				communication_medium="Email",
				send_email=False,
				attachments=attachments,
				cc=cc,
				bcc=bcc,
				communication_type="Automated Message",
			).get("name")
			# set the outgoing email account because we did in fact send it via sendmail above
			comm = frappe.get_lazy_doc("Communication", communication)
			comm.get_outgoing_email_account()

		frappe.sendmail(
			recipients=recipients,
			subject=subject,
			sender=sender,
			cc=cc,
			bcc=bcc,
			message=message,
			reference_doctype=get_reference_doctype(doc),
			reference_name=get_reference_name(doc),
			attachments=attachments,
			expose_recipients="header",
			print_letterhead=((attachments and attachments[0].get("print_letterhead")) or False),
			communication=communication,
		)

	def send_a_slack_msg(self, doc, context):
		send_slack_message(
			webhook_url=self.slack_webhook_url,
			message=frappe.render_template(self.message, context),
			reference_doctype=get_reference_doctype(doc),
			reference_name=get_reference_name(doc),
		)

	def send_sms(self, doc, context):
		send_sms(
			receiver_list=self.get_receiver_list(doc, context, "mobile_no", self.get_mobile_no),
			msg=frappe.utils.strip_html_tags(frappe.render_template(self.message, context)),
		)

	@staticmethod
	def get_mobile_no(doc, field):
		option = doc.meta.get_field(field).options.strip()
		# users may sometimes register mobile numbers under Phone type fields
		if option == "Phone" or option == "Mobile":
			mobile_no = doc.get(field)
			if not mobile_no:
				doc.log_error(
					_("Notification: document {0} has no {1} number set (field: {2})").format(
						field, doc.name, option, field
					)
				)
		# but on user & customer it's expected to be set on the proper field
		elif option == "User":
			user = doc.get(field)
			mobile_no = frappe.get_value("User", user, "mobile_no")
			if not mobile_no:
				doc.log_error(_("Notification: user {0} has no Mobile number set").format(user))
		elif option == "Customer":
			customer = doc.get(field)
			mobile_no = frappe.get_value("Customer", customer, "mobile_no")
			if not mobile_no:
				doc.log_error(_("Notification: customer {0} has no Mobile number set").format(customer))
		else:
			frappe.throw(
				_(
					"Field {0} on document {1} is neither a Mobile number field nor a Customer or User link"
				).format(field, doc.name)
			)
		return mobile_no

	def get_list_of_recipients(self, doc, context):
		recipients = []
		cc = []
		bcc = []
		for recipient in self.recipients:
			if recipient.condition:
				if not frappe.safe_eval(recipient.condition, None, context):
					continue
			if recipient.receiver_by_document_field:
				data_field, child_field = _parse_receiver_by_document_field(
					recipient.receiver_by_document_field
				)
				if child_field:
					for d in doc.get(child_field):
						email_id = d.get(data_field)
						if validate_email_address(email_id):
							recipients.append(email_id)
				# field from current doc
				else:
					email_ids_value = doc.get(data_field)
					if validate_email_address(email_ids_value):
						email_ids = email_ids_value.replace(",", "\n")
						recipients = recipients + email_ids.split("\n")

			cc.extend(get_emails_from_template(recipient.cc, context))
			bcc.extend(get_emails_from_template(recipient.bcc, context))

			# For sending emails to specified role
			if recipient.receiver_by_role:
				emails = get_info_based_on_role(recipient.receiver_by_role, "email", ignore_permissions=True)

				for email in emails:
					recipients = recipients + email.split("\n")

		if self.send_to_all_assignees:
			recipients = recipients + get_assignees(doc)

		return list(set(recipients)), list(set(cc)), list(set(bcc))

	def get_receiver_list(self, doc, context, field_on_user="mobile_no", recipient_extractor_func=None):
		"""return receiver list based on the doc field and role specified"""
		if not recipient_extractor_func:
			recipient_extractor_func = self.get_mobile_no
		receiver_list = []
		for recipient in self.recipients:
			if recipient.condition:
				if not frappe.safe_eval(recipient.condition, None, context):
					continue

			# For sending messages to the owner's mobile phone number
			if recipient.receiver_by_document_field == "owner":
				receiver_list += get_user_info([dict(user_name=doc.get("owner"))], field_on_user)
			# For sending messages to the number specified in the receiver field
			elif recipient.receiver_by_document_field:
				data_field, child_field = _parse_receiver_by_document_field(
					recipient.receiver_by_document_field
				)
				if child_field:
					for d in doc.get(child_field):
						if recv := recipient_extractor_func(d, data_field):
							receiver_list.append(recv)
				# field from current doc
				else:
					if recv := recipient_extractor_func(doc, data_field):
						receiver_list.append(recv)

			# For sending messages to specified role
			if recipient.receiver_by_role:
				receiver_list += get_info_based_on_role(
					recipient.receiver_by_role, field_on_user, ignore_permissions=True
				)

		return list(set(receiver_list))

	def get_attachment(self, doc):
		"""check print settings are attach the pdf"""
		if not self.attach_print:
			return None

		print_settings = frappe.get_doc("Print Settings", "Print Settings")
		if (doc.docstatus == 0 and not print_settings.allow_print_for_draft) or (
			doc.docstatus == 2 and not print_settings.allow_print_for_cancelled
		):
			# ignoring attachment as draft and cancelled documents are not allowed to print
			status = "Draft" if doc.docstatus == 0 else "Cancelled"
			frappe.throw(
				_(
					"""Not allowed to attach {0} document, please enable Allow Print For {0} in Print Settings"""
				).format(status),
				title=_("Error in Notification"),
			)
		else:
			return [
				{
					"print_format_attachment": 1,
					"doctype": doc.doctype,
					"name": doc.name,
					"print_format": self.print_format,
					"print_letterhead": print_settings.with_letterhead,
					"lang": frappe.db.get_value("Print Format", self.print_format, "default_print_language")
					if self.print_format
					else "en",
				}
			]

	def get_template(self, md_as_html=False):
		module = get_doc_module(self.module, self.doctype, self.name)

		path = os.path.join(os.path.dirname(module.__file__), frappe.scrub(self.name))
		extension = FORMATS.get(self.message_type, ".md")
		file_path = path + extension

		template = ""

		if os.path.exists(file_path):
			with open(file_path) as f:
				template = f.read()

		if not template:
			return

		if extension == ".md":
			return frappe.utils.md_to_html(template)

		return template

	def load_standard_properties(self, context):
		"""load templates and run get_context"""
		module = get_doc_module(self.module, self.doctype, self.name)
		if module:
			if hasattr(module, "get_context"):
				out = module.get_context(context)
				if out:
					context.update(out)

		self.message = self.get_template(md_as_html=True)

	def on_trash(self):
		clear_notification_cache()


def clear_notification_cache():
	frappe.client_cache.delete_keys("notifications::")


@frappe.whitelist()
def get_documents_for_today(notification):
	notification = frappe.get_doc("Notification", notification)
	notification.check_permission("read")
	return [d.name for d in notification.get_documents_for_today()]


def trigger_offset_alerts():
	trigger_notifications(None, "offset")


def trigger_daily_alerts():
	trigger_notifications(None, "daily")


def trigger_notifications(doc, method=None):
	if frappe.flags.in_import or frappe.flags.in_patch:
		# don't send notifications while syncing or patching
		return

	if method == "daily":
		doc_list = frappe.get_all(
			"Notification", filters={"event": ("in", ("Days Before", "Days After")), "enabled": 1}
		)
		for d in doc_list:
			alert = frappe.get_doc("Notification", d.name)

			for doc in alert.get_documents_for_today():
				evaluate_alert(doc, alert, alert.event)
				#  this is the end of the transaction in the alert trigger stack
				frappe.db.commit()  # nosemgrep

	elif method == "offset":
		doc_list = frappe.get_all(
			"Notification", filters={"event": ("in", ("Minutes Before", "Minutes After")), "enabled": 1}
		)
		for d in doc_list:
			alert = frappe.get_doc("Notification", d.name)

			for doc in alert.get_documents_for_this_moment():
				evaluate_alert(doc, alert, alert.event)
				#  this is the end of the transaction in the alert trigger stack
				frappe.db.commit()  # nosemgrep


def evaluate_alert(doc: Document, alert, event=None):
	from jinja2 import TemplateError

	try:
		if isinstance(alert, str):
			alert = frappe.get_doc("Notification", alert)

		context = get_context(doc)

		if alert.condition_type == "Python" and alert.condition:
			if not frappe.safe_eval(alert.condition, None, context):
				return
		elif alert.condition_type == "Filters" and alert.filters:
			if not evaluate_filters(doc, json.loads(alert.filters)):
				return

		if event == "Value Change" and not doc.is_new():
			if not frappe.db.has_column(doc.doctype, alert.value_changed):
				alert.db_set("enabled", 0)
				alert.log_error(f"Notification {alert.name} has been disabled due to missing field")
				return

			doc_before_save = doc.get_doc_before_save()
			field_value_before_save = doc_before_save.get(alert.value_changed) if doc_before_save else None

			fieldtype = doc.meta.get_field(alert.value_changed).fieldtype
			if cast(fieldtype, doc.get(alert.value_changed)) == cast(fieldtype, field_value_before_save):
				# value not changed
				return

		if event != "Value Change" and not doc.is_new():
			# reload the doc for the latest values & comments,
			# except for validate type event.
			doc.reload()
		alert.send(doc)
	except TemplateError:
		message = _("Error while evaluating Notification {0}. Please fix your template.").format(
			frappe.utils.get_link_to_form("Notification", alert.name)
		)
		frappe.throw(message, title=_("Error in Notification"))
	except Exception as e:
		title = str(e)
		message = frappe.get_traceback(with_context=True)
		frappe.log_error(title=title, message=message)
		msg = f"<details><summary>{title}</summary>{message}</details>"
		frappe.throw(msg, title=_("Error in Notification"))


def get_context(doc):
	Frappe = namedtuple("Frappe", ["frappe"])
	frappe = Frappe(frappe=get_safe_globals().get("frappe"))
	return {
		"doc": doc,
		"nowdate": nowdate,
		"frappe": frappe.frappe,
	}


def get_assignees(doc):
	assignees = []
	assignees = frappe.get_all(
		"ToDo",
		filters={"status": "Open", "reference_name": doc.name, "reference_type": doc.doctype},
		fields=["allocated_to"],
	)

	return [d.allocated_to for d in assignees]


def get_emails_from_template(template, context):
	if not template:
		return ()

	emails = frappe.render_template(template, context) if "{" in template else template
	return filter(None, emails.replace(",", "\n").split("\n"))


def get_reference_doctype(doc):
	return doc.parenttype if doc.meta.istable else doc.doctype


def get_reference_name(doc):
	return doc.parent if doc.meta.istable else doc.name


def _parse_receiver_by_document_field(s):
	fragments = s.split(",")
	# fields from child table or linked doctype
	if len(fragments) > 1:
		data_field, child_field = fragments
	else:
		data_field, child_field = fragments[0], None
	return data_field, child_field
