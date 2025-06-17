# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

from datetime import timedelta

from dateutil.relativedelta import relativedelta

import frappe
from frappe import _
from frappe.automation.doctype.assignment_rule.assignment_rule import get_repeated
from frappe.contacts.doctype.contact.contact import (
	get_contacts_linked_from,
	get_contacts_linking_to,
)
from frappe.core.doctype.communication.email import make
from frappe.desk.form import assign_to
from frappe.model.document import Document
from frappe.utils import (
	add_days,
	cstr,
	get_first_day,
	get_last_day,
	getdate,
	month_diff,
	split_emails,
	today,
)
from frappe.utils.background_jobs import get_jobs
from frappe.utils.jinja import validate_template
from frappe.utils.user import get_system_managers

month_map = {"Monthly": 1, "Quarterly": 3, "Half-yearly": 6, "Yearly": 12}
week_map = {
	"Monday": 0,
	"Tuesday": 1,
	"Wednesday": 2,
	"Thursday": 3,
	"Friday": 4,
	"Saturday": 5,
	"Sunday": 6,
}


class AutoRepeat(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.automation.doctype.auto_repeat_day.auto_repeat_day import AutoRepeatDay
		from frappe.types import DF

		disabled: DF.Check
		end_date: DF.Date | None
		frequency: DF.Literal["", "Daily", "Weekly", "Monthly", "Quarterly", "Half-yearly", "Yearly"]
		message: DF.Text | None
		next_schedule_date: DF.Date | None
		notify_by_email: DF.Check
		print_format: DF.Link | None
		recipients: DF.SmallText | None
		reference_doctype: DF.Link
		reference_document: DF.DynamicLink
		repeat_on_day: DF.Int
		repeat_on_days: DF.Table[AutoRepeatDay]
		repeat_on_last_day: DF.Check
		start_date: DF.Date
		status: DF.Literal["", "Active", "Disabled", "Completed"]
		subject: DF.Data | None
		submit_on_creation: DF.Check
		template: DF.Link | None
	# end: auto-generated types

	def validate(self):
		self.update_status()
		self.validate_reference_doctype()
		self.validate_submit_on_creation()
		self.validate_dates()
		self.validate_email_id()
		self.validate_auto_repeat_days()
		self.set_dates()
		self.update_auto_repeat_id()
		self.unlink_if_applicable()

		validate_template(self.subject or "")
		validate_template(self.message or "")

	def before_insert(self):
		if not frappe.in_test:
			start_date = getdate(self.start_date)
			today_date = getdate(today())
			if start_date <= today_date:
				self.start_date = today_date

	def on_update(self):
		frappe.get_doc(self.reference_doctype, self.reference_document).notify_update()

	def on_trash(self):
		frappe.db.set_value(self.reference_doctype, self.reference_document, "auto_repeat", "")
		frappe.get_doc(self.reference_doctype, self.reference_document).notify_update()

	def set_dates(self):
		if self.disabled:
			self.next_schedule_date = None
		else:
			self.next_schedule_date = self.get_next_schedule_date(schedule_date=self.start_date)
			if self.end_date and getdate(self.end_date) < getdate(self.next_schedule_date):
				frappe.throw(_("The Next Scheduled Date cannot be later than the End Date."))

	def unlink_if_applicable(self):
		if self.status == "Completed" or self.disabled:
			frappe.db.set_value(self.reference_doctype, self.reference_document, "auto_repeat", "")

	def validate_reference_doctype(self):
		if frappe.in_test or frappe.flags.in_patch:
			return
		if not frappe.get_meta(self.reference_doctype).allow_auto_repeat:
			frappe.throw(
				_("Enable Allow Auto Repeat for the doctype {0} in Customize Form").format(
					self.reference_doctype
				)
			)

	def validate_submit_on_creation(self):
		if self.submit_on_creation and not frappe.get_meta(self.reference_doctype).is_submittable:
			frappe.throw(
				_("Cannot enable {0} for a non-submittable doctype").format(
					frappe.bold(_("Submit on Creation"))
				)
			)

	def validate_dates(self):
		if frappe.flags.in_patch:
			return

		if self.end_date:
			self.validate_from_to_dates("start_date", "end_date")

		if self.end_date == self.start_date:
			frappe.throw(
				_("{0} should not be same as {1}").format(
					frappe.bold(_("End Date")), frappe.bold(_("Start Date"))
				)
			)

	def validate_email_id(self):
		if self.notify_by_email:
			if self.recipients:
				email_list = split_emails(self.recipients.replace("\n", ""))
				from frappe.utils import validate_email_address

				for email in email_list:
					if not validate_email_address(email):
						frappe.throw(_("{0} is an invalid email address in 'Recipients'").format(email))
			else:
				frappe.throw(_("'Recipients' not specified"))

	def validate_auto_repeat_days(self):
		auto_repeat_days = self.get_auto_repeat_days()
		if len(set(auto_repeat_days)) != len(auto_repeat_days):
			repeated_days = get_repeated(auto_repeat_days)
			plural = "s" if len(repeated_days) > 1 else ""

			frappe.throw(
				_("Auto Repeat Day{0} {1} has been repeated.").format(
					plural, frappe.bold(", ".join(repeated_days))
				)
			)

	def update_auto_repeat_id(self):
		# check if document is already on auto repeat
		auto_repeat = frappe.db.get_value(self.reference_doctype, self.reference_document, "auto_repeat")
		if auto_repeat and auto_repeat != self.name and not frappe.flags.in_patch:
			frappe.throw(
				_("The {0} is already on auto repeat {1}").format(self.reference_document, auto_repeat)
			)
		else:
			frappe.db.set_value(self.reference_doctype, self.reference_document, "auto_repeat", self.name)

	def update_status(self):
		if self.disabled:
			self.status = "Disabled"
		elif self.is_completed():
			self.status = "Completed"
		else:
			self.status = "Active"

	def is_completed(self):
		return self.end_date and getdate(self.end_date) < getdate(today())

	@frappe.whitelist()
	def get_auto_repeat_schedule(self):
		schedule_details = []
		start_date = getdate(self.start_date)
		end_date = getdate(self.end_date)

		if not self.end_date:
			next_date = self.get_next_schedule_date(schedule_date=start_date)
			row = {
				"reference_document": self.reference_document,
				"frequency": self.frequency,
				"next_scheduled_date": next_date,
			}
			schedule_details.append(row)

		if self.end_date:
			next_date = self.get_next_schedule_date(schedule_date=start_date, for_full_schedule=True)

			while getdate(next_date) <= getdate(end_date):
				row = {
					"reference_document": self.reference_document,
					"frequency": self.frequency,
					"next_scheduled_date": next_date,
				}
				schedule_details.append(row)
				next_date = self.get_next_schedule_date(schedule_date=next_date, for_full_schedule=True)

		return schedule_details

	def create_documents(self):
		try:
			new_doc = self.make_new_document()
			if self.notify_by_email and self.recipients:
				self.send_notification(new_doc)
		except Exception:
			error_log = self.log_error(
				_("Auto repeat failed. Please enable auto repeat after fixing the issues.")
			)

			self.disable_auto_repeat()

			if self.reference_document and not frappe.in_test:
				self.notify_error_to_user(error_log)

	def make_new_document(self):
		reference_doc = frappe.get_doc(self.reference_doctype, self.reference_document)
		new_doc = frappe.copy_doc(reference_doc, ignore_no_copy=False)
		self.update_doc(new_doc, reference_doc)
		new_doc.flags.updater_reference = {
			"doctype": self.doctype,
			"docname": self.name,
			"label": _("via Auto Repeat"),
		}
		new_doc.insert(ignore_permissions=True)

		if self.submit_on_creation:
			new_doc.submit()

		return new_doc

	def update_doc(self, new_doc, reference_doc):
		new_doc.docstatus = 0
		if new_doc.meta.get_field("set_posting_time"):
			new_doc.set("set_posting_time", 1)

		if new_doc.meta.get_field("auto_repeat"):
			new_doc.set("auto_repeat", self.name)

		for fieldname in [
			"naming_series",
			"ignore_pricing_rule",
			"posting_time",
			"select_print_heading",
			"user_remark",
			"remarks",
			"owner",
		]:
			if new_doc.meta.get_field(fieldname):
				new_doc.set(fieldname, reference_doc.get(fieldname))

		for data in new_doc.meta.fields:
			if data.fieldtype == "Date" and data.reqd:
				new_doc.set(data.fieldname, self.next_schedule_date)

		self.set_auto_repeat_period(new_doc)

		auto_repeat_doc = frappe.get_doc("Auto Repeat", self.name)

		# for any action that needs to take place after the recurring document creation
		# on recurring method of that doctype is triggered
		new_doc.run_method("on_recurring", reference_doc=reference_doc, auto_repeat_doc=auto_repeat_doc)

	def set_auto_repeat_period(self, new_doc):
		mcount = month_map.get(self.frequency)
		if mcount and new_doc.meta.get_field("from_date") and new_doc.meta.get_field("to_date"):
			last_ref_doc = frappe.get_all(
				doctype=self.reference_doctype,
				fields=["name", "from_date", "to_date"],
				filters=[
					["auto_repeat", "=", self.name],
					["docstatus", "<", 2],
				],
				order_by="creation desc",
				limit=1,
			)

			if not last_ref_doc:
				return

			from_date = get_next_date(last_ref_doc[0].from_date, mcount)

			if (cstr(get_first_day(last_ref_doc[0].from_date)) == cstr(last_ref_doc[0].from_date)) and (
				cstr(get_last_day(last_ref_doc[0].to_date)) == cstr(last_ref_doc[0].to_date)
			):
				to_date = get_last_day(get_next_date(last_ref_doc[0].to_date, mcount))
			else:
				to_date = get_next_date(last_ref_doc[0].to_date, mcount)

			new_doc.set("from_date", from_date)
			new_doc.set("to_date", to_date)

	def get_next_schedule_date(self, schedule_date, for_full_schedule=False):
		"""
		Return the next schedule date for auto repeat after a recurring document has been created.
		Add required offset to the schedule_date param and return the next schedule date.

		:param schedule_date: The date when the last recurring document was created.
		:param for_full_schedule: If True, return the immediate next schedule date, else the full schedule.
		"""
		if month_map.get(self.frequency):
			month_count = month_map.get(self.frequency) + month_diff(schedule_date, self.start_date) - 1
		else:
			month_count = 0

		day_count = 0
		if month_count:
			day_count = 31 if self.repeat_on_last_day else self.repeat_on_day or None
			next_date = get_next_date(self.start_date, month_count, day_count)
		else:
			days = self.get_days(schedule_date)
			next_date = add_days(schedule_date, days)

		# next schedule date should be after or on current date
		if not for_full_schedule:
			while getdate(next_date) < getdate(today()):
				if month_count:
					month_count += month_map.get(self.frequency, 0)
					next_date = get_next_date(self.start_date, month_count, day_count)
				else:
					days = self.get_days(next_date)
					next_date = add_days(next_date, days)

			if self.end_date and getdate(next_date) > getdate(self.end_date):
				next_date = schedule_date

		return next_date

	def get_days(self, schedule_date):
		if self.frequency == "Weekly":
			days = self.get_offset_for_weekly_frequency(schedule_date)
		else:
			# daily frequency
			days = 1

		return days

	def get_offset_for_weekly_frequency(self, schedule_date):
		# if weekdays are not set, offset is 7 from current schedule date
		if not self.repeat_on_days:
			return 7

		repeat_on_days = self.get_auto_repeat_days()
		current_schedule_day = getdate(schedule_date).weekday()
		weekdays = list(week_map.keys())

		# if repeats on more than 1 day or
		# start date's weekday is not in repeat days, then get next weekday
		# else offset is 7
		if len(repeat_on_days) > 1 or weekdays[current_schedule_day] not in repeat_on_days:
			weekday = get_next_weekday(current_schedule_day, repeat_on_days)
			next_weekday_number = week_map.get(weekday, 0)
			# offset for upcoming weekday
			return timedelta((7 + next_weekday_number - current_schedule_day) % 7).days
		return 7

	def get_auto_repeat_days(self):
		return [d.day for d in self.get("repeat_on_days", [])]

	def send_notification(self, new_doc):
		"""Notify concerned people about recurring document generation"""
		subject = self.subject or ""
		message = self.message or ""

		if not self.subject:
			subject = _("New {0}: {1}").format(new_doc.doctype, new_doc.name)
		elif "{" in self.subject:
			subject = frappe.render_template(self.subject, {"doc": new_doc})

		print_format = self.print_format or "Standard"
		error_string = None

		try:
			attachments = [
				frappe.attach_print(
					new_doc.doctype, new_doc.name, file_name=new_doc.name, print_format=print_format
				)
			]

		except frappe.PermissionError:
			error_string = _("A recurring {0} {1} has been created for you via Auto Repeat {2}.").format(
				new_doc.doctype, new_doc.name, self.name
			)
			error_string += "<br><br>"

			error_string += _(
				"{0}: Failed to attach new recurring document. To enable attaching document in the auto repeat notification email, enable {1} in Print Settings"
			).format(frappe.bold(_("Note")), frappe.bold(_("Allow Print for Draft")))
			attachments = None

		if error_string:
			message = error_string
		elif not self.message:
			message = _("Please find attached {0}: {1}").format(new_doc.doctype, new_doc.name)
		elif "{" in self.message:
			message = frappe.render_template(self.message, {"doc": new_doc})

		make(
			doctype=new_doc.doctype,
			name=new_doc.name,
			recipients=self.recipients,
			subject=subject,
			content=message,
			attachments=attachments,
			send_email=1,
		)

	@frappe.whitelist()
	def fetch_linked_contacts(self):
		if self.reference_doctype and self.reference_document:
			res = get_contacts_linking_to(
				self.reference_doctype, self.reference_document, fields=["email_id"]
			)
			res += get_contacts_linked_from(
				self.reference_doctype, self.reference_document, fields=["email_id"]
			)
			email_ids = {d.email_id for d in res}
			if not email_ids:
				frappe.msgprint(_("No contacts linked to document"), alert=True)
			else:
				self.recipients = ", ".join(email_ids)

	def disable_auto_repeat(self):
		frappe.db.set_value("Auto Repeat", self.name, "disabled", 1)

	def notify_error_to_user(self, error_log):
		recipients = list(get_system_managers(only_name=True))
		recipients.append(self.owner)
		subject = _("Auto Repeat Document Creation Failed")

		form_link = frappe.utils.get_link_to_form(self.reference_doctype, self.reference_document)
		auto_repeat_failed_for = _("Auto Repeat failed for {0}").format(form_link)

		error_log_link = frappe.utils.get_link_to_form("Error Log", error_log.name)
		error_log_message = _("Check the Error Log for more information: {0}").format(error_log_link)

		frappe.sendmail(
			recipients=recipients,
			subject=subject,
			template="auto_repeat_fail",
			args={"auto_repeat_failed_for": auto_repeat_failed_for, "error_log_message": error_log_message},
			header=[subject, "red"],
		)


def get_next_date(dt, mcount, day=None):
	dt = getdate(dt)
	dt += relativedelta(months=mcount, day=day)
	return dt


def get_next_weekday(current_schedule_day, weekdays):
	days = list(week_map.keys())
	if current_schedule_day > 0:
		days = days[(current_schedule_day + 1) :] + days[:current_schedule_day]
	else:
		days = days[(current_schedule_day + 1) :]

	for entry in days:
		if entry in weekdays:
			return entry


# called through hooks
def make_auto_repeat_entry():
	enqueued_method = "frappe.automation.doctype.auto_repeat.auto_repeat.create_repeated_entries"
	jobs = get_jobs()

	if not jobs or enqueued_method not in jobs[frappe.local.site]:
		date = getdate(today())
		data = get_auto_repeat_entries(date)
		frappe.enqueue(enqueued_method, data=data, queue="long")


def create_repeated_entries(data):
	for d in data:
		doc = frappe.get_doc("Auto Repeat", d.name)

		current_date = getdate(today())
		schedule_date = getdate(doc.next_schedule_date)

		if schedule_date == current_date and not doc.disabled:
			doc.create_documents()
			schedule_date = doc.get_next_schedule_date(schedule_date=schedule_date)
			if schedule_date and not doc.disabled:
				frappe.db.set_value("Auto Repeat", doc.name, "next_schedule_date", schedule_date)

		if doc.is_completed():
			doc.status = "Completed"
			doc.save()


def get_auto_repeat_entries(date=None):
	if not date:
		date = getdate(today())

	auto_repeat = frappe.qb.DocType("Auto Repeat")
	query = frappe.qb.from_(auto_repeat)
	query = query.select("name")
	query = query.where(
		(auto_repeat.next_schedule_date <= date)
		& (auto_repeat.status == "Active")
		& ((auto_repeat.end_date >= auto_repeat.next_schedule_date) | (auto_repeat.end_date.isnull()))
	)
	return query.run(as_dict=1)


@frappe.whitelist()
def make_auto_repeat(doctype, docname, frequency="Daily", start_date=None, end_date=None):
	if not start_date:
		start_date = getdate(today())
	doc = frappe.new_doc("Auto Repeat")
	doc.reference_doctype = doctype
	doc.reference_document = docname
	doc.frequency = frequency
	doc.start_date = start_date
	if end_date:
		doc.end_date = end_date
	doc.save()
	return doc


# method for reference_doctype filter
@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_auto_repeat_doctypes(doctype, txt, searchfield, start, page_len, filters):
	res = frappe.get_all(
		"Property Setter",
		{
			"property": "allow_auto_repeat",
			"value": "1",
		},
		["doc_type"],
	)
	docs = [r.doc_type for r in res]

	res = frappe.get_all(
		"DocType",
		{
			"allow_auto_repeat": 1,
		},
		["name"],
	)
	docs += [r.name for r in res]
	docs = set(list(docs))

	return [[d] for d in docs if txt in d]


@frappe.whitelist()
def update_reference(docname: str, reference: str):
	doc = frappe.get_doc("Auto Repeat", str(docname))
	doc.check_permission("write")
	doc.db_set("reference_document", str(reference))
	return "success"  # backward compatbility


@frappe.whitelist()
def generate_message_preview(reference_dt, reference_doc, message=None, subject=None):
	frappe.has_permission("Auto Repeat", "write", throw=True)
	doc = frappe.get_doc(reference_dt, reference_doc)
	doc.check_permission()
	subject_preview = _("Please add a subject to your email")
	msg_preview = frappe.render_template(message, {"doc": doc})
	if subject:
		subject_preview = frappe.render_template(subject, {"doc": doc})

	return {"message": msg_preview, "subject": subject_preview}
