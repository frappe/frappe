# Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import nts
import nts.desk.form.assign_to
from nts.automation.doctype.assignment_rule.test_assignment_rule import (
	TEST_DOCTYPE,
	_make_test_record,
	create_test_doctype,
)
from nts.desk.form.load import get_assignments
from nts.desk.listview import get_group_by_count
from nts.tests.utils import ntsTestCase


class TestAssign(ntsTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_test_doctype(TEST_DOCTYPE)

	def test_assign(self):
		todo = nts.get_doc({"doctype": "ToDo", "description": "test"}).insert()
		if not nts.db.exists("User", "test@example.com"):
			nts.get_doc({"doctype": "User", "email": "test@example.com", "first_name": "Test"}).insert()

		self._test_basic_assign_on_document(todo)

	def _test_basic_assign_on_document(self, doc):
		added = assign(doc, "test@example.com")

		self.assertTrue("test@example.com" in [d.owner for d in added])

		nts.desk.form.assign_to.remove(doc.doctype, doc.name, "test@example.com")

		# assignment is cleared
		assignments = nts.desk.form.assign_to.get(dict(doctype=doc.doctype, name=doc.name))
		self.assertEqual(len(assignments), 0)

	def test_assign_single(self):
		c = nts.get_doc("Contact Us Settings")
		self._test_basic_assign_on_document(c)

	def test_assignment_count(self):
		nts.db.delete("ToDo")

		if not nts.db.exists("User", "test_assign1@example.com"):
			nts.get_doc(
				{
					"doctype": "User",
					"email": "test_assign1@example.com",
					"first_name": "Test",
					"roles": [{"role": "System Manager"}],
				}
			).insert()

		if not nts.db.exists("User", "test_assign2@example.com"):
			nts.get_doc(
				{
					"doctype": "User",
					"email": "test_assign2@example.com",
					"first_name": "Test",
					"roles": [{"role": "System Manager"}],
				}
			).insert()

		note = _make_test_record()
		assign(note, "test_assign1@example.com")

		note = _make_test_record(public=1)
		assign(note, "test_assign2@example.com")

		note = _make_test_record(public=1)
		assign(note, "test_assign2@example.com")

		note = _make_test_record()
		assign(note, "test_assign2@example.com")

		data = {d.name: d.count for d in get_group_by_count(TEST_DOCTYPE, "[]", "assigned_to")}

		self.assertTrue("test_assign1@example.com" in data)
		self.assertEqual(data["test_assign1@example.com"], 1)
		self.assertEqual(data["test_assign2@example.com"], 3)

		data = {d.name: d.count for d in get_group_by_count(TEST_DOCTYPE, '[{"public": 1}]', "assigned_to")}

		self.assertFalse("test_assign1@example.com" in data)
		self.assertEqual(data["test_assign2@example.com"], 2)

		nts.db.rollback()

	def test_assignment_removal(self):
		todo = nts.get_doc({"doctype": "ToDo", "description": "test"}).insert()
		if not nts.db.exists("User", "test@example.com"):
			nts.get_doc({"doctype": "User", "email": "test@example.com", "first_name": "Test"}).insert()

		new_todo = assign(todo, "test@example.com")

		# remove assignment
		nts.db.set_value("ToDo", new_todo[0].name, "allocated_to", "")

		self.assertFalse(get_assignments("ToDo", todo.name))


def assign(doc, user):
	return nts.desk.form.assign_to.add(
		{
			"assign_to": [user],
			"doctype": doc.doctype,
			"name": doc.name,
			"description": "test",
		}
	)
