# Copyright (c) 2018, Frappe Technologies and Contributors
# License: MIT. See LICENSE
from typing import TYPE_CHECKING

import frappe
from frappe.automation.doctype.auto_repeat.auto_repeat import (
	create_repeated_entries,
	get_auto_repeat_entries,
	update_reference,
	week_map,
)
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.tests import IntegrationTestCase
from frappe.tests.test_model_utils import set_user
from frappe.utils import add_days, add_months, getdate, today

if TYPE_CHECKING:
	from frappe.custom.doctype.custom_field.custom_field import CustomField


def add_custom_fields() -> "CustomField":
	df = dict(
		fieldname="auto_repeat",
		label="Auto Repeat",
		fieldtype="Link",
		insert_after="sender",
		options="Auto Repeat",
		hidden=1,
		print_hide=1,
		read_only=1,
	)
	return create_custom_field("ToDo", df) or frappe.get_doc(
		"Custom Field", dict(fieldname=df["fieldname"], dt="ToDo")
	)


class TestAutoRepeat(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		cls.custom_field = add_custom_fields()
		cls.addClassCleanup(cls.custom_field.delete)
		return super().setUpClass()

	def test_daily_auto_repeat(self):
		todo = frappe.get_doc(
			doctype="ToDo", description="test recurring todo", assigned_by="Administrator"
		).insert()

		doc = make_auto_repeat(reference_document=todo.name)
		self.assertEqual(doc.next_schedule_date, today())
		data = get_auto_repeat_entries(getdate(today()))
		create_repeated_entries(data)
		frappe.db.commit()

		todo = frappe.get_doc(doc.reference_doctype, doc.reference_document)
		self.assertEqual(todo.auto_repeat, doc.name)

		new_todo = frappe.db.get_value("ToDo", {"auto_repeat": doc.name, "name": ("!=", todo.name)}, "name")

		new_todo = frappe.get_doc("ToDo", new_todo)

		self.assertEqual(todo.get("description"), new_todo.get("description"))

	def test_weekly_auto_repeat(self):
		todo = frappe.get_doc(
			doctype="ToDo", description="test weekly todo", assigned_by="Administrator"
		).insert()

		doc = make_auto_repeat(
			reference_doctype="ToDo",
			frequency="Weekly",
			reference_document=todo.name,
			start_date=add_days(today(), -7),
		)

		self.assertEqual(doc.next_schedule_date, today())
		data = get_auto_repeat_entries(getdate(today()))
		create_repeated_entries(data)
		frappe.db.commit()

		todo = frappe.get_doc(doc.reference_doctype, doc.reference_document)
		self.assertEqual(todo.auto_repeat, doc.name)

		new_todo = frappe.db.get_value("ToDo", {"auto_repeat": doc.name, "name": ("!=", todo.name)}, "name")

		new_todo = frappe.get_doc("ToDo", new_todo)

		self.assertEqual(todo.get("description"), new_todo.get("description"))

	def test_fortnightly_auto_repeat(self):
		todo = frappe.get_doc(
			doctype="ToDo", description="test fortnightly todo", assigned_by="Administrator"
		).insert()

		doc = make_auto_repeat(
			reference_doctype="ToDo",
			frequency="Fortnightly",
			reference_document=todo.name,
			start_date=add_days(today(), -14),
		)

		self.assertEqual(doc.next_schedule_date, today())
		data = get_auto_repeat_entries(getdate(today()))
		create_repeated_entries(data)
		frappe.db.commit()

		todo = frappe.get_doc(doc.reference_doctype, doc.reference_document)
		self.assertEqual(todo.auto_repeat, doc.name)

		new_todo = frappe.db.get_value("ToDo", {"auto_repeat": doc.name, "name": ("!=", todo.name)}, "name")

		new_todo = frappe.get_doc("ToDo", new_todo)

		self.assertEqual(todo.get("description"), new_todo.get("description"))

	def test_weekly_auto_repeat_with_weekdays(self):
		todo = frappe.get_doc(
			doctype="ToDo", description="test auto repeat with weekdays", assigned_by="Administrator"
		).insert()

		weekdays = list(week_map.keys())
		current_weekday = getdate().weekday()
		days = [{"day": weekdays[current_weekday]}, {"day": weekdays[(current_weekday + 2) % 7]}]
		doc = make_auto_repeat(
			reference_doctype="ToDo",
			frequency="Weekly",
			reference_document=todo.name,
			start_date=add_days(today(), -7),
			days=days,
		)

		self.assertEqual(doc.next_schedule_date, today())
		data = get_auto_repeat_entries(getdate(today()))
		create_repeated_entries(data)
		frappe.db.commit()

		todo = frappe.get_doc(doc.reference_doctype, doc.reference_document)
		self.assertEqual(todo.auto_repeat, doc.name)

		doc.reload()
		self.assertEqual(doc.next_schedule_date, add_days(getdate(), 2))

	def test_monthly_auto_repeat(self):
		start_date = today()
		end_date = add_months(start_date, 12)

		todo = frappe.get_doc(
			doctype="ToDo", description="test recurring todo", assigned_by="Administrator"
		).insert()

		self.monthly_auto_repeat("ToDo", todo.name, start_date, end_date)
		# test without end_date
		todo = frappe.get_doc(
			doctype="ToDo", description="test recurring todo without end_date", assigned_by="Administrator"
		).insert()
		self.monthly_auto_repeat("ToDo", todo.name, start_date)

	def monthly_auto_repeat(self, doctype, docname, start_date, end_date=None):
		def get_months(start, end):
			diff = (12 * end.year + end.month) - (12 * start.year + start.month)
			return diff + 1

		doc = make_auto_repeat(
			reference_doctype=doctype,
			frequency="Monthly",
			reference_document=docname,
			start_date=start_date,
			end_date=end_date,
		)

		doc.disable_auto_repeat()

		data = get_auto_repeat_entries(getdate(today()))
		create_repeated_entries(data)
		docnames = frappe.get_all(doc.reference_doctype, {"auto_repeat": doc.name})
		self.assertEqual(len(docnames), 1)

		doc = frappe.get_doc("Auto Repeat", doc.name)
		doc.db_set("disabled", 0)

		months = get_months(getdate(start_date), getdate(today()))
		data = get_auto_repeat_entries(getdate(today()))
		create_repeated_entries(data)

		docnames = frappe.get_all(doc.reference_doctype, {"auto_repeat": doc.name})
		self.assertEqual(len(docnames), months)

	def test_email_notification(self):
		todo = frappe.get_doc(
			doctype="ToDo", description="Test recurring notification attachment", assigned_by="Administrator"
		).insert()

		doc = make_auto_repeat(
			reference_document=todo.name,
			notify=1,
			recipients="test@domain.com",
			subject="New ToDo",
			message="A new ToDo has just been created for you",
		)
		data = get_auto_repeat_entries(getdate(today()))
		create_repeated_entries(data)
		frappe.db.commit()

		new_todo = frappe.db.get_value("ToDo", {"auto_repeat": doc.name, "name": ("!=", todo.name)}, "name")

		email_queue = frappe.db.exists("Email Queue", dict(reference_doctype="ToDo", reference_name=new_todo))
		self.assertTrue(email_queue)

	def test_next_schedule_date(self):
		current_date = getdate(today())
		todo = frappe.get_doc(
			doctype="ToDo", description="test next schedule date for monthly", assigned_by="Administrator"
		).insert()
		doc = make_auto_repeat(
			frequency="Monthly", reference_document=todo.name, start_date=add_months(today(), -2)
		)

		# next_schedule_date is set as on or after current date
		# it should not be a previous month's date
		self.assertTrue(doc.next_schedule_date >= current_date)

		todo = frappe.get_doc(
			doctype="ToDo", description="test next schedule date for daily", assigned_by="Administrator"
		).insert()
		doc = make_auto_repeat(
			frequency="Daily", reference_document=todo.name, start_date=add_days(today(), -2)
		)
		self.assertEqual(getdate(doc.next_schedule_date), current_date)

	def test_submit_on_creation(self):
		doctype = "Test Submittable DocType"
		create_submittable_doctype(doctype)

		current_date = getdate()
		submittable_doc = frappe.get_doc(doctype=doctype, test="test submit on creation").insert()
		submittable_doc.submit()
		doc = make_auto_repeat(
			frequency="Daily",
			reference_doctype=doctype,
			reference_document=submittable_doc.name,
			start_date=add_days(current_date, -1),
			submit_on_creation=1,
		)

		data = get_auto_repeat_entries(current_date)
		create_repeated_entries(data)
		docnames = frappe.get_all(
			doc.reference_doctype, filters={"auto_repeat": doc.name}, fields=["docstatus"], limit=1
		)
		self.assertEqual(docnames[0].docstatus, 1)

	def test_reference_document_write_permission_on_create(self):
		todo = frappe.get_doc(
			doctype="ToDo", description="test reference permission", assigned_by="Administrator"
		).insert()
		user = create_user_without_reference_access()

		self.assertFalse(frappe.has_permission("ToDo", "write", todo.name, user=user))

		with set_user(user):
			auto_repeat = frappe.get_doc(
				doctype="Auto Repeat",
				reference_doctype="ToDo",
				reference_document=todo.name,
				frequency="Daily",
				start_date=today(),
			)
			auto_repeat.validate_reference_doctype()
			self.assertRaises(frappe.PermissionError, auto_repeat.validate_reference_permission)
			self.assertRaises(frappe.PermissionError, auto_repeat.insert)

		self.assertFalse(frappe.db.get_value("ToDo", todo.name, "auto_repeat"))

	def test_deleted_reference_does_not_stop_the_scheduler(self):
		todo = frappe.get_doc(
			doctype="ToDo", description="test reference permission", assigned_by="Administrator"
		).insert()
		owner = "test_auto_repeat_owner@example.com"
		if not frappe.db.exists("User", owner):
			frappe.get_doc(
				doctype="User",
				email=owner,
				first_name="Auto Repeat Owner",
				send_welcome_email=0,
				roles=[{"role": "System Manager"}],
			).insert(ignore_permissions=True)

		doc = make_auto_repeat(reference_document=todo.name)
		frappe.db.set_value("Auto Repeat", doc.name, "owner", owner)
		doc.reload()
		frappe.delete_doc("ToDo", todo.name, force=True, ignore_permissions=True)

		doc.create_documents()

		self.assertTrue(frappe.db.get_value("Auto Repeat", doc.name, "disabled"))

	def test_auto_repeat_stays_active_when_owner_loses_reference_access(self):
		todo = frappe.get_doc(
			doctype="ToDo", description="test reference permission", assigned_by="Administrator"
		).insert()
		user = create_user_without_reference_access()

		doc = make_auto_repeat(reference_document=todo.name)
		frappe.db.set_value("Auto Repeat", doc.name, "owner", user)
		doc.reload()

		doc.create_documents()

		self.assertFalse(frappe.db.exists("ToDo", {"auto_repeat": doc.name, "name": ("!=", todo.name)}))
		self.assertFalse(frappe.db.get_value("Auto Repeat", doc.name, "disabled"))

	def test_reference_document_write_permission_on_update_reference(self):
		todo = frappe.get_doc(
			doctype="ToDo", description="test reference permission", assigned_by="Administrator"
		).insert()
		user = create_user_without_reference_access()

		own_todo = frappe.get_doc(
			doctype="ToDo", description="test reference permission", allocated_to=user, owner=user
		).insert()
		doc = make_auto_repeat(reference_document=own_todo.name)
		frappe.db.set_value("Auto Repeat", doc.name, "owner", user)

		with set_user(user):
			self.assertRaises(frappe.PermissionError, update_reference, doc.name, todo.name)

		self.assertNotEqual(frappe.db.get_value("Auto Repeat", doc.name, "reference_document"), todo.name)

	def test_auto_repeat_assignee(self):
		todo = frappe.get_doc(
			doctype="ToDo", description="test assignee todo", assigned_by="Administrator"
		).insert()

		doc = make_auto_repeat(reference_document=todo.name)
		doc.update(
			{
				"assignee": [
					{"user": "Administrator"},
					{"user": "Guest"},
				]
			}
		)
		doc.save()
		self.assertEqual(doc.next_schedule_date, today())
		data = get_auto_repeat_entries(getdate(today()))
		create_repeated_entries(data)
		frappe.db.commit()

		todo = frappe.get_doc(doc.reference_doctype, doc.reference_document)
		self.assertEqual(todo.auto_repeat, doc.name)

		new_todo = frappe.db.get_value("ToDo", {"auto_repeat": doc.name, "name": ("!=", todo.name)}, "name")

		new_todo = frappe.get_doc("ToDo", new_todo)
		self.assertEqual(todo.get("description"), new_todo.get("description"))
		self.assertListEqual(
			sorted(list(new_todo.get_assigned_users())),
			sorted(["Administrator", "Guest"]),
		)

	def test_auto_repeat_assignee_with_separate_documents(self):
		todo = frappe.get_doc(
			doctype="ToDo",
			description="test assignee todo with multiple doc",
			assigned_by="Administrator",
		).insert()

		doc = make_auto_repeat(reference_document=todo.name)
		doc.update(
			{
				"assignee": [
					{"user": "Administrator"},
					{"user": "Guest"},
				],
				"generate_separate_documents_for_each_assignee": 1,
			}
		)
		doc.save()
		self.assertEqual(doc.next_schedule_date, today())
		data = get_auto_repeat_entries(getdate(today()))
		create_repeated_entries(data)
		frappe.db.commit()

		todo = frappe.get_doc(doc.reference_doctype, doc.reference_document)
		self.assertEqual(todo.auto_repeat, doc.name)

		new_todo_count = frappe.db.count("ToDo", {"auto_repeat": doc.name, "name": ("!=", todo.name)}, "name")

		self.assertEqual(new_todo_count, 2)


def make_auto_repeat(**args):
	args = frappe._dict(args)
	return frappe.get_doc(
		{
			"doctype": "Auto Repeat",
			"reference_doctype": args.reference_doctype or "ToDo",
			"reference_document": args.reference_document or frappe.db.get_value("ToDo", "name"),
			"submit_on_creation": args.submit_on_creation or 0,
			"frequency": args.frequency or "Daily",
			"start_date": args.start_date or add_days(today(), -1),
			"end_date": args.end_date or "",
			"notify_by_email": args.notify or 0,
			"recipients": args.recipients or "",
			"subject": args.subject or "",
			"message": args.message or "",
			"repeat_on_days": args.days or [],
		}
	).insert(ignore_permissions=True)


def create_user_without_reference_access():
	"""Return a user who can create an Auto Repeat but cannot access another user's ToDo."""
	email = "test_auto_repeat_reference@example.com"
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			doctype="User",
			email=email,
			first_name="Auto Repeat Reference",
			send_welcome_email=0,
			roles=[{"role": "Accounts User"}],
		).insert(ignore_permissions=True)
		frappe.clear_cache(user=email)

	return email


def create_submittable_doctype(doctype, submit_perms=1):
	if frappe.db.exists("DocType", doctype):
		return
	else:
		doc = frappe.get_doc(
			{
				"doctype": "DocType",
				"__newname": doctype,
				"module": "Custom",
				"custom": 1,
				"is_submittable": 1,
				"fields": [{"fieldname": "test", "label": "Test", "fieldtype": "Data"}],
				"permissions": [
					{
						"role": "System Manager",
						"read": 1,
						"write": 1,
						"create": 1,
						"delete": 1,
						"submit": submit_perms,
						"cancel": submit_perms,
						"amend": submit_perms,
					}
				],
			}
		).insert()

		doc.allow_auto_repeat = 1
		doc.save()
