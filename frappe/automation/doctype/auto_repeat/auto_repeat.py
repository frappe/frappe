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
	def validate(self):
		self.update_status()
		self.validate_reference_doctype()
		self.validate_dates()
		self.validate_email_id()
		self.set_dates()
		self.update_auto_repeat_id()
		self.unlink_if_applicable()

		validate_template(self.subject or "")
		validate_template(self.message or "")

	def before_insert(self):
		today_date = today()
		if self.start_date <= today_date:
			self.start_date = today_date

	def after_save(self):
		frappe.get_doc(self.reference_doctype, self.reference_document).notify_update()

	def on_trash(self):
		frappe.db.set_value(self.reference_doctype, self.reference_document, {
			'auto_repeat': self.name
		}, 'auto_repeat', '')

	def set_dates(self):
		if self.disabled:
			self.next_schedule_date = None
		else:
			self.next_schedule_date = get_next_schedule_date(self.start_date, self.frequency, self.repeat_on_day, self.repeat_on_last_day, self.end_date)

	def unlink_if_applicable(self):
		if self.status == 'Completed' or self.disabled:
			frappe.db.set_value(self.reference_doctype, self.reference_document, "auto_repeat", '')

	def validate_reference_doctype(self):
		if not frappe.get_meta(self.reference_doctype).has_field('auto_repeat'):
			frappe.throw(_("Enable Allow Auto Repeat for the doctype {0} in Customize Form").format(self.reference_doctype))

	def validate_dates(self):
		self.validate_from_to_dates('start_date', 'end_date')

		if self.end_date == self.start_date:
			frappe.throw(_('{0} should not be same as {1}').format(frappe.bold('End Date'), frappe.bold('Start Date')))

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

	def update_auto_repeat_id(self):
		#check if document is already on auto repeat
		auto_repeat = frappe.db.get_value(self.reference_doctype, self.reference_document, "auto_repeat")
		if auto_repeat and auto_repeat != self.name:
			frappe.throw(_("The {0} is already on auto repeat {1}").format(self.reference_document, auto_repeat))
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

	def get_auto_repeat_schedule(self):
		schedule_details = []
		start_date = getdate(self.start_date)
		end_date = getdate(self.end_date)
		today = frappe.utils.datetime.date.today()

		if start_date < today:
			start_date = today

		if not self.end_date:
			start_date = get_next_schedule_date(start_date, self.frequency, self.repeat_on_day, self.repeat_on_last_day)
			row = {
				"reference_document": self.reference_document,
				"frequency": self.frequency,
				"next_scheduled_date": start_date
			}
			schedule_details.append(row)
			start_date = get_next_schedule_date(start_date, self.frequency, self.repeat_on_day, self.repeat_on_last_day)

		if self.end_date:
			start_date = get_next_schedule_date(start_date, self.frequency, self.repeat_on_day, self.repeat_on_last_day)
			while (getdate(start_date) < getdate(end_date)):
				row = {
					"reference_document" : self.reference_document,
					"frequency" : self.frequency,
					"next_scheduled_date" : start_date
				}
				schedule_details.append(row)
				start_date = get_next_schedule_date(start_date, self.frequency, self.repeat_on_day, self.repeat_on_last_day, end_date)


		return schedule_details


def get_next_schedule_date(start_date, frequency, repeat_on_day, repeat_on_last_day = False, end_date = None):
	mcount = month_map.get(frequency)
	if mcount and repeat_on_last_day:
		last_day = 31
		next_date = get_next_date(start_date, mcount, last_day)
	elif mcount and repeat_on_day:
		next_date = get_next_date(start_date, mcount, repeat_on_day)
	elif mcount:
		next_date = get_next_date(start_date, mcount)
	else:
		days = 7 if frequency == 'Weekly' else 1
		next_date = add_days(start_date, days)

	return next_date

def make_auto_repeat_entry():
	enqueued_method = 'frappe.automation.doctype.auto_repeat.auto_repeat.create_repeated_entries'
	jobs = get_jobs()

	if not jobs or enqueued_method not in jobs[frappe.local.site]:
		date = today()
		data = get_auto_repeat_entries(date)
		frappe.enqueue(enqueued_method, data=data)

def create_repeated_entries(data):
	for d in data:
		doc = frappe.get_doc('Auto Repeat', d.name)

		current_date = getdate(today())
		schedule_date = getdate(doc.next_schedule_date)

		while schedule_date <= current_date and not doc.disabled:
			create_documents(doc, schedule_date)
			schedule_date = get_next_schedule_date(schedule_date, doc.frequency, doc.repeat_on_day, doc.repeat_on_last_day, doc.end_date)

			if schedule_date and not doc.disabled:
				frappe.db.set_value('Auto Repeat', doc.name, 'next_schedule_date', schedule_date)
				frappe.db.commit()

def get_auto_repeat_entries(date=None):
	date = today()
	return frappe.db.get_all('Auto Repeat', filters=[
		['next_schedule_date', '<=', date],
		['status', '=', 'Active']
	])

def set_auto_repeat_as_completed():
	auto_repeat = frappe.get_all("Auto Repeat", filters = {'status': ['!=', 'Disabled']})
	for entry in auto_repeat:
		doc = frappe.get_doc("Auto Repeat", entry.name)
		if doc.is_completed():
			doc.status = 'Completed'
			doc.save()

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
def make_auto_repeat(doctype, docname, frequency, start_date, end_date = None):
	doc = frappe.new_doc('Auto Repeat')
	doc.reference_doctype = doctype
	doc.reference_document = docname
	doc.frequency = frequency
	doc.start_date = start_date
	if end_date:
		doc.end_date = end_date
	doc.save()
	return doc

def get_auto_repeat_doctypes(doctype, txt, searchfield, start, page_len, filters):
	repeatable_docs = []
	docs = [d for d in frappe.db.get_values("DocType", {"issingle": 0, "istable": 0, "hide_toolbar": 0})]
	for dt in docs:
		if frappe.get_meta(dt[0]).allow_auto_repeat == 1:
			repeatable_docs.append([dt[0]])
	return repeatable_docs

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
