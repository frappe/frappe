# Copyright (c) 2018, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
import os

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.modules.utils import export_module_json, get_doc_module
from frappe.utils import add_to_date, cast, nowdate, validate_email_address
from frappe.utils.safe_exec import get_safe_globals

FORMATS = {"HTML": ".html", "Markdown": ".md", "Plain Text": ".txt"}


class Notification(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.email.doctype.notification_recipient.notification_recipient import (
			NotificationRecipient,
		)
		from frappe.types import DF

		attach_print: DF.Check
		channel: DF.Literal["Email", "Slack", "System Notification", "SMS"]
		condition: DF.Code | None
		date_changed: DF.Literal
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
			"Value Change",
			"Method",
			"Custom",
		]
		is_standard: DF.Check
		message: DF.Code | None
		message_type: DF.Literal["Markdown", "HTML", "Plain Text"]
		method: DF.Data | None
		module: DF.Link | None
		print_format: DF.Link | None
		property_value: DF.Data | None
		recipients: DF.Table[NotificationRecipient]
		send_system_notification: DF.Check
		send_to_all_assignees: DF.Check
		sender: DF.Link | None
		sender_email: DF.Data | None
		set_property_after_alert: DF.Literal
		slack_webhook_url: DF.Link | None
		subject: DF.Data | None
		value_changed: DF.Literal
	# end: auto-generated types
	def onload(self):
		"""load message"""
		if self.is_standard:
			self.message = self.get_template()

	def autoname(self):
		if not self.name:
			self.name = self.subject

	def validate(self):
		notification_channels_per_app = frappe.get_hooks("notification_channels")
		for notification_channels in notification_channels_per_app:
			channel = notification_channels.get(self.channel)
			method = channel.get("validate")
			frappe.get_attr(method)(self)

		if self.event in ("Days Before", "Days After") and not self.date_changed:
			frappe.throw(_("Please specify which date field must be checked"))

		if self.event == "Value Change" and not self.value_changed:
			frappe.throw(_("Please specify which value field must be checked"))

		self.validate_forbidden_types()
		self.validate_condition()
		self.validate_standard()
		frappe.cache.hdel("notifications", self.document_type)

	def on_update(self):
		frappe.cache.hdel("notifications", self.document_type)
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

	def validate_condition(self):
		temp_doc = frappe.new_doc(self.document_type)
		if self.condition:
			try:
				frappe.safe_eval(self.condition, None, get_context(temp_doc.as_dict()))
			except Exception:
				frappe.throw(_("The Condition '{0}' is invalid").format(self.condition))

	def validate_forbidden_types(self):
		forbidden_document_types = ("Email Queue",)
		if self.document_type in forbidden_document_types or frappe.get_meta(self.document_type).istable:
			# currently notifications don't work on child tables as events are not fired for each record of child table

			frappe.throw(_("Cannot set Notification on Document Type {0}").format(self.document_type))

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

		for d in doc_list:
			doc = frappe.get_doc(self.document_type, d.name)

			if self.condition and not frappe.safe_eval(self.condition, None, get_context(doc)):
				continue

			docs.append(doc)

		return docs

	def send(self, doc):
		"""Build recipients and send Notification"""

		context = get_context(doc)
		context = {"doc": doc, "alert": self, "comments": None}
		if doc.get("_comments"):
			context["comments"] = json.loads(doc.get("_comments"))

		if self.is_standard:
			self.load_standard_properties(context)
		try:
			notification_channels_per_app = frappe.get_hooks("notification_channels")
			for notification_channels in notification_channels_per_app:
				channel = notification_channels.get(self.channel)
				method = channel.get("send")
				frappe.get_attr(method)(self, doc, context)
				# only send once - ignore redefinitions in other apps
				break

			if self.send_system_notification:
				from .system_notification import send

				send(self, doc, context)

		except Exception:
			self.log_error("Failed to send Notification")

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
		frappe.cache.hdel("notifications", self.document_type)


@frappe.whitelist()
def get_documents_for_today(notification):
	notification = frappe.get_doc("Notification", notification)
	notification.check_permission("read")
	return [d.name for d in notification.get_documents_for_today()]


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
				frappe.db.commit()


def evaluate_alert(doc: Document, alert, event):
	from jinja2 import TemplateError

	try:
		if isinstance(alert, str):
			alert = frappe.get_doc("Notification", alert)

		context = get_context(doc)

		if alert.condition:
			if not frappe.safe_eval(alert.condition, None, context):
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
		message = frappe.get_traceback()
		frappe.log_error(message=message, title=title)

		msg = f"<details><summary>{title}</summary>{message}</details>"
		frappe.throw(msg, title=_("Error in Notification"))


def get_context(doc):
	return {
		"doc": doc,
		"nowdate": nowdate,
		"frappe": frappe._dict(utils=get_safe_globals().get("frappe").get("utils")),
	}
