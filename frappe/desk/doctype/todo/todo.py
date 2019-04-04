# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import json
import calendar

from frappe.model.document import Document
from frappe.utils import get_fullname
from frappe.utils.background_jobs import enqueue

from frappe import _
from frappe.utils.data import add_to_date, getdate

subject_field = "description"
sender_field = "sender"
exclude_from_linked_with = True


class ToDo(Document):
	def check_date(self):
		if self.start_date > self.date:
			frappe.throw(_("Start Date over Due Date is not allowed"))
		elif self.start_date == self.date:
			frappe.throw(_("Start Date same as Due Date is not allowed"))

	def check_delta_frequency(self):
		start = getdate(self.start_date)
		end = getdate(self.date)

		if self.frequency == "Weekly" and (add_to_date(start, days=7) > end):
			frappe.throw(_("Date range is not allowed, should be at least 7 days"))
		if self.frequency == "Monthly" and (add_to_date(start, months=1) > end):
			frappe.throw(_("Date range is not allowed, should be at least 1 month"))

	def validate(self):
		self._assignment = None

		if self.is_recurring:
			self.check_date()
			self.check_delta_frequency()

		if self.is_new():
			if self.assigned_by == self.owner:
				assignment_message = frappe._("{0} self assigned this task: {1}").format(get_fullname(self.assigned_by), self.description)
			else:
				assignment_message = frappe._("{0} assigned {1}: {2}").format(get_fullname(self.assigned_by), get_fullname(self.owner), self.description)

			self._assignment = {
				"text": assignment_message,
				"comment_type": "Assigned"
			}

		else:
			# NOTE the previous value is only available in validate method
			if self.get_db_value("status") != self.status:
				self._assignment = {
					"text": frappe._("Assignment closed by {0}".format(get_fullname(frappe.session.user))),
					"comment_type": "Assignment Completed"
				}

	def on_update(self):
		if self._assignment:
			self.add_assign_comment(**self._assignment)

		self.update_in_reference()

	def after_insert(self):
		if self.is_recurring:
			enqueue(make_recurred_todo, doc=self)

	def on_trash(self):
		# unlink todo from linked comments
		frappe.db.sql("""update `tabCommunication` set link_doctype=null, link_name=null
			where link_doctype=%(doctype)s and link_name=%(name)s""", {"doctype": self.doctype, "name": self.name})

		self.update_in_reference()

	def add_assign_comment(self, text, comment_type):
		if not (self.reference_type and self.reference_name):
			return

		frappe.get_doc(self.reference_type, self.reference_name).add_comment(comment_type, text)

	def update_in_reference(self):
		if not (self.reference_type and self.reference_name):
			return

		try:
			assignments = [d[0] for d in frappe.get_all("ToDo",
				filters={
					"reference_type": self.reference_type,
					"reference_name": self.reference_name,
					"status": "Open"
				},
				fields=["owner"], as_list=True)]

			assignments.reverse()
			frappe.db.set_value(self.reference_type, self.reference_name,
				"_assign", json.dumps(assignments), update_modified=False)

		except Exception as e:
			if frappe.db.is_table_missing(e) and frappe.flags.in_install:
				# no table
				return

			elif frappe.db.is_column_missing(e):
				from frappe.database.schema import add_column
				add_column(self.reference_type, "_assign", "Text")
				self.update_in_reference()

			else:
				raise


# NOTE: todo is viewable if either owner or assigned_to or System Manager in roles
def on_doctype_update():
	frappe.db.add_index("ToDo", ["reference_type", "reference_name"])


def get_permission_query_conditions(user):
	if not user: user = frappe.session.user

	if "System Manager" in frappe.get_roles(user):
		return None
	else:
		return """(tabToDo.owner = {user} or tabToDo.assigned_by = {user})"""\
			.format(user=frappe.db.escape(user))


def has_permission(doc, user):
	if "System Manager" in frappe.get_roles(user):
		return True
	else:
		return doc.owner == user or doc.assigned_by == user


def get_interval_days(frequency):
	days = {
		"Daily": 1,
		"Weekdays": 1,
		"Weekly": 7,
		"Monthly": 30
	}
	return days[frequency]


def is_weekend(date):
	return date.weekday() in [calendar.SATURDAY, calendar.SUNDAY]


def make_recurred_todo(doc):
	iterdate = getdate(doc.start_date)
	interval = get_interval_days(doc.frequency)
	months, days = divmod(interval, 30)

	while iterdate < getdate(doc.date):
		iterdate = add_to_date(iterdate, days=days, months=months)

		if doc.frequency == "Weekdays" and is_weekend(iterdate):
			continue

		frappe.get_doc({
			'doctype': 'ToDo',
			'priority': doc.priority,
			'color': doc.color,
			'owner': doc.owner,
			'date': iterdate,
			'description': doc.description,
			'reference_type': doc.reference_type,
			'reference_name': doc.reference_name,
			'role': doc.role,
			'assigned_by': doc.assigned_by
		}).insert()


@frappe.whitelist()
def new_todo(description):
	frappe.get_doc({
		'doctype': 'ToDo',
		'description': description
	}).insert()
