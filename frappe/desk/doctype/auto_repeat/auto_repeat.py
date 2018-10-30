# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import calendar
from frappe import _
from frappe.desk.form import assign_to
from frappe.utils.jinja import validate_template
from dateutil.relativedelta import relativedelta
from frappe.utils.user import get_system_managers
from frappe.utils import cstr, getdate, split_emails, add_days, today, get_last_day, get_first_day
from frappe.model.document import Document
from frappe.core.doctype.communication.email import make
from frappe.utils.background_jobs import get_jobs

month_map = {'Monthly': 1, 'Quarterly': 3, 'Half-yearly': 6, 'Yearly': 12}


class AutoRepeat(Document):
	def onload(self):
		self.set_onload("auto_repeat_schedule", self.get_auto_repeat_schedule())

	def validate(self):
		self.update_status()
		self.validate_reference_doctype()
		self.validate_dates()
		self.validate_next_schedule_date()
		self.validate_email_id()
		self.link_party()

		validate_template(self.subject or "")
		validate_template(self.message or "")

	def before_submit(self):
		if not self.next_schedule_date:
			self.next_schedule_date = get_next_schedule_date(
				self.start_date, self.frequency, self.repeat_on_day)

	def on_submit(self):
		self.update_auto_repeat_id()

	def on_update_after_submit(self):
		self.validate_dates()
		self.set_next_schedule_date()

	def before_cancel(self):
		self.unlink_auto_repeat_id()
		self.next_schedule_date = None

	def unlink_auto_repeat_id(self):
		frappe.db.sql(
			"update `tab{0}` set auto_repeat = null where auto_repeat=%s".format(self.reference_doctype), self.name)

	def validate_reference_doctype(self):
		if not frappe.get_meta(self.reference_doctype).has_field('auto_repeat'):
			frappe.throw(_("Add custom field Auto Repeat in the doctype {0}").format(self.reference_doctype))

	def validate_dates(self):
		if self.end_date and getdate(self.start_date) > getdate(self.end_date):
			frappe.throw(_("End date must be greater than start date"))

	def validate_next_schedule_date(self):
		if self.repeat_on_day and self.next_schedule_date:
			next_date = getdate(self.next_schedule_date)
			if next_date.day != self.repeat_on_day:
				# if the repeat day is the last day of the month (31)
				# and the current month does not have as many days,
				# then the last day of the current month is a valid date
				lastday = calendar.monthrange(next_date.year, next_date.month)[1]
				if self.repeat_on_day < lastday:
					# the specified day of the month is not same as the day specified
					# or the last day of the month
					frappe.throw(_("Next Date's day and Repeat on Day of Month must be equal"))

	def validate_email_id(self):
		if self.notify_by_email:
			if self.recipients:
				email_list = split_emails(self.recipients.replace("\n", ""))

				from frappe.utils import validate_email_add
				for email in email_list:
					if not validate_email_add(email):
						frappe.throw(_("{0} is an invalid email address in 'Recipients'").format(email))
			else:
				frappe.throw(_("'Recipients' not specified"))

	def set_next_schedule_date(self):
		if self.repeat_on_day:
			self.next_schedule_date = get_next_date(self.next_schedule_date, 0, self.repeat_on_day)

	def update_auto_repeat_id(self):
		frappe.db.set_value(self.reference_doctype, self.reference_document, "auto_repeat", self.name)

	def update_status(self, status=None):
		self.status = {
			'0': 'Draft',
			'1': 'Submitted',
			'2': 'Cancelled'
		}[cstr(self.docstatus or 0)]

		if status and status != 'Resumed':
			self.status = status

	def get_auto_repeat_schedule(self):
		schedule_details = []
		start_date_copy = getdate(self.start_date)
		end_date_copy = getdate(self.end_date)
		today_copy = frappe.utils.datetime.date.today()

		if start_date_copy < today_copy:
			start_date_copy = today_copy

		if not self.end_date:
			days = 60 if self.frequency in ['Daily', 'Weekly'] else 365
			end_date_copy = add_days(today_copy, days)

		while (getdate(start_date_copy) < getdate(end_date_copy)):
			start_date_copy = get_next_schedule_date(start_date_copy, self.frequency, self.repeat_on_day)
			row = {
				"reference_document" : self.reference_document,
				"frequency" : self.frequency,
				"next_scheduled_date" : start_date_copy
			}
			schedule_details.append(row)

		return schedule_details

	def link_party(self):
		reference = frappe.get_meta(self.reference_doctype)
		for field in reference.fields:
			if field.options in ['Customer', 'Supplier', 'Employee']:
				self.reference_party_doctype = field.options
				self.reference_party = frappe.db.get_value(self.reference_doctype, self.reference_document, field.fieldname)
				break

def get_next_schedule_date(start_date, frequency, repeat_on_day):
	mcount = month_map.get(frequency)
	if mcount:
		next_date = get_next_date(start_date, mcount, repeat_on_day)
	else:
		days = 7 if frequency == 'Weekly' else 1
		next_date = add_days(start_date, days)
	return next_date

def make_auto_repeat_entry(date=None):
	enqueued_method = 'frappe.desk.doctype.auto_repeat.auto_repeat.create_repeated_entries'
	jobs = get_jobs()

	if not jobs or enqueued_method not in jobs[frappe.local.site]:
		date = date or today()
		for data in get_auto_repeat_entries(date):
			frappe.enqueue(enqueued_method, data=data)

def create_repeated_entries(data):
	schedule_date = getdate(data.next_schedule_date)
	while schedule_date <= getdate(today()) and not frappe.db.get_value('Auto Repeat', data.name, 'disabled'):
		create_documents(data, schedule_date)
		schedule_date = get_next_schedule_date(schedule_date, data.frequency, data.repeat_on_day)

		if schedule_date and not frappe.db.get_value('Auto Repeat', data.name, 'disabled'):
			frappe.db.set_value('Auto Repeat', data.name, 'next_schedule_date', schedule_date)
			frappe.db.commit()

def get_auto_repeat_entries(date):
	return frappe.db.sql(""" select * from `tabAuto Repeat`
		where docstatus = 1 and next_schedule_date <=%s
			and reference_document is not null and reference_document != ''
			and next_schedule_date <= ifnull(end_date, '2199-12-31')
			and disabled = 0 and status != 'Stopped' """, (date), as_dict=1)

def create_documents(data, schedule_date):
	try:
		doc = make_new_document(data, schedule_date)
		if data.notify_by_email and data.recipients:
			print_format = data.print_format or "Standard"
			send_notification(doc, data, print_format=print_format)

		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		frappe.db.begin()
		frappe.log_error(frappe.get_traceback(), _("Recurring document creation failure"))
		disable_auto_repeat(data)
		frappe.db.commit()
		if data.reference_document and not frappe.flags.in_test:
			notify_error_to_user(data)

def disable_auto_repeat(data):
	auto_repeat = frappe.get_doc('Auto Repeat', data.name)
	auto_repeat.db_set('disabled', 1)

def notify_error_to_user(data):
	party = ''
	party_type = ''

	if data.reference_doctype in ['Sales Order', 'Sales Invoice', 'Delivery Note']:
		party_type = 'customer'
	elif data.reference_doctype in ['Purchase Order', 'Purchase Invoice', 'Purchase Receipt']:
		party_type = 'supplier'

	if party_type:
		party = frappe.db.get_value(data.reference_doctype, data.reference_document, party_type)

	notify_errors(data.reference_document, data.reference_doctype, party, data.owner, data.name)

def make_new_document(args, schedule_date):
	doc = frappe.get_doc(args.reference_doctype, args.reference_document)
	new_doc = frappe.copy_doc(doc, ignore_no_copy=False)
	update_doc(new_doc, doc, args, schedule_date)
	new_doc.insert(ignore_permissions=True)

	if args.submit_on_creation:
		new_doc.submit()

	return new_doc

def update_doc(new_document, reference_doc, args, schedule_date):
	new_document.docstatus = 0
	if new_document.meta.get_field('set_posting_time'):
		new_document.set('set_posting_time', 1)

	mcount = month_map.get(args.frequency)

	if new_document.meta.get_field('auto_repeat'):
		new_document.set('auto_repeat', args.name)

	for fieldname in ['naming_series', 'ignore_pricing_rule', 'posting_time',
						'select_print_heading', 'remarks', 'owner']:
		if new_document.meta.get_field(fieldname):
			new_document.set(fieldname, reference_doc.get(fieldname))

	# copy item fields
	if new_document.meta.get_field('items'):
		for i, item in enumerate(new_document.items):
			for fieldname in ("page_break",):
				item.set(fieldname, reference_doc.items[i].get(fieldname))

	for data in new_document.meta.fields:
		if data.fieldtype == 'Date' and data.reqd:
			new_document.set(data.fieldname, schedule_date)

	set_auto_repeat_period(args, mcount, new_document)

	new_document.run_method("on_recurring", reference_doc=reference_doc, auto_repeat_doc=args)

def set_auto_repeat_period(args, mcount, new_document):
	if mcount and new_document.meta.get_field('from_date') and new_document.meta.get_field('to_date'):
		last_ref_doc = frappe.db.sql("""
			select name, from_date, to_date
			from `tab{0}`
			where auto_repeat=%s and docstatus < 2
			order by creation desc
			limit 1
		""".format(args.reference_doctype), args.name, as_dict=1)

		if not last_ref_doc:
			return

		from_date = get_next_date(last_ref_doc[0].from_date, mcount)

		if (cstr(get_first_day(last_ref_doc[0].from_date)) == cstr(last_ref_doc[0].from_date)) and \
				(cstr(get_last_day(last_ref_doc[0].to_date)) == cstr(last_ref_doc[0].to_date)):
			to_date = get_last_day(get_next_date(last_ref_doc[0].to_date, mcount))
		else:
			to_date = get_next_date(last_ref_doc[0].to_date, mcount)

		new_document.set('from_date', from_date)
		new_document.set('to_date', to_date)

def get_next_date(dt, mcount, day=None):
	dt = getdate(dt)
	dt += relativedelta(months=mcount, day=day)

	return dt

def send_notification(new_rv, auto_repeat_doc, print_format='Standard'):
	"""Notify concerned persons about recurring document generation"""
	print_format = print_format
	subject = auto_repeat_doc.subject or ''
	message = auto_repeat_doc.message or ''

	if not auto_repeat_doc.subject:
		subject = _("New {0}: #{1}").format(new_rv.doctype, new_rv.name)
	elif "{" in auto_repeat_doc.subject:
		subject = frappe.render_template(auto_repeat_doc.subject, {'doc': new_rv})

	if not auto_repeat_doc.message:
		message = _("Please find attached {0} #{1}").format(new_rv.doctype, new_rv.name)
	elif "{" in auto_repeat_doc.message:
		message = frappe.render_template(auto_repeat_doc.message, {'doc': new_rv})

	attachments = [frappe.attach_print(new_rv.doctype, new_rv.name,
						file_name=new_rv.name, print_format=print_format)]

	make(doctype=new_rv.doctype, name=new_rv.name, recipients=auto_repeat_doc.recipients,
					subject=subject, content=message, attachments=attachments, send_email=1)

def notify_errors(doc, doctype, party, owner, name):
	recipients = get_system_managers(only_name=True)
	frappe.sendmail(recipients + [frappe.db.get_value("User", owner, "email")],
					subject=_("[Urgent] Error while creating recurring %s for %s" % (doctype, doc)),
					message=frappe.get_template("templates/emails/recurring_document_failed.html").render({
						"type": _(doctype),
						"name": doc,
						"party": party or "",
						"auto_repeat": name
					}))
	try:
		assign_task_to_owner(name, _("Recurring Documents Failed"), recipients)
	except Exception:
		frappe.log_error(frappe.get_traceback(), _("Recurring Documents Failed"))

def assign_task_to_owner(name, msg, users):
	for d in users:
		args = {
			'doctype': 'Auto Repeat',
			'assign_to': d,
			'name':	name,
			'description': msg,
			'priority': 'High'
		}
		assign_to.add(args)

@frappe.whitelist()
def make_auto_repeat(doctype, docname):
	doc = frappe.new_doc('Auto Repeat')

	reference_doc = frappe.get_doc(doctype, docname)
	doc.reference_doctype = doctype
	doc.reference_document = docname
	doc.start_date = reference_doc.get('posting_date') or reference_doc.get('transaction_date')
	return doc

@frappe.whitelist()
def stop_resume_auto_repeat(auto_repeat, status):
	doc = frappe.get_doc('Auto Repeat', auto_repeat)
	frappe.msgprint(_("Auto Repeat has been {0}").format(status))
	if status == 'Resumed':
		doc.next_schedule_date = get_next_schedule_date(today(),
			doc.frequency, doc.repeat_on_day)

	doc.update_status(status)
	doc.save()

	return doc.status

def auto_repeat_doctype_query(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""select parent from `tabDocField`
		where fieldname = 'auto_repeat'
			and parent like %(txt)s
		order by
			if(locate(%(_txt)s, parent), locate(%(_txt)s, parent), 99999),
			parent
		limit %(start)s, %(page_len)s""".format(**{
			'key': searchfield,
		}), {
			'txt': "%%%s%%" % txt,
			'_txt': txt.replace("%", ""),
			'start': start,
			'page_len': page_len
		})

@frappe.whitelist()
def get_contacts(reference_doctype, reference_name):
	docfields = frappe.get_meta(reference_doctype).fields

	contact_fields = []
	for field in docfields:
		if field.fieldtype == "Link" and field.options == "Contact":
			contact_fields.append(field.fieldname)

	if contact_fields:
		contacts = []
		for contact_field in contact_fields:
			contacts.append(frappe.db.get_value(reference_doctype, reference_name, contact_field))
	else:
		return []

	if contacts:
		emails = []
		for contact in contacts:
			emails.append(frappe.db.get_value("Contact", contact, "email_id"))

		return emails
	else:
		return []


@frappe.whitelist()
def update_reference(docname, reference):
	try:
		frappe.db.set_value("Auto Repeat", docname, "reference_document", reference)
		return "success"
	except Exception as e:
		raise e
		return "error"

@frappe.whitelist()
def generate_message_preview(reference_dt, reference_doc, message=None, subject=None):
	doc = frappe.get_doc(reference_dt, reference_doc)
	subject_preview = _("Please add a subject to your email")
	msg_preview = frappe.render_template(message, {'doc': doc})
	if subject:
		subject_preview = frappe.render_template(subject, {'doc': doc})

	return {'message': msg_preview, 'subject': subject_preview}
