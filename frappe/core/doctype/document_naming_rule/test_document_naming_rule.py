# Copyright (c) 2020, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.patches.v16_0.seed_naming_rule_series import execute as seed_naming_rule_series
from frappe.patches.v16_0.seed_naming_rule_series import seed_series_for_rule
from frappe.query_builder import DocType
from frappe.tests import IntegrationTestCase


class TestDocumentNamingRule(IntegrationTestCase):
	def test_naming_rule_by_series(self):
		naming_rule = frappe.get_doc(
			doctype="Document Naming Rule", document_type="ToDo", prefix="test-todo-", prefix_digits=5
		).insert()

		todo = frappe.get_doc(
			doctype="ToDo", description="Is this my name " + frappe.generate_hash()
		).insert()

		self.assertEqual(todo.name, "test-todo-00001")

		naming_rule.delete()
		todo.delete()

	def test_naming_rule_by_condition(self):
		naming_rule = frappe.get_doc(
			doctype="Document Naming Rule",
			document_type="ToDo",
			prefix="test-high-",
			prefix_digits=5,
			priority=10,
			conditions=[dict(field="priority", condition="=", value="High")],
		).insert()

		# another rule
		naming_rule_1 = frappe.copy_doc(naming_rule)
		naming_rule_1.prefix = "test-medium-"
		naming_rule_1.conditions[0].value = "Medium"
		naming_rule_1.insert()

		# default rule with low priority - should not get applied for rules
		# with higher priority
		naming_rule_2 = frappe.copy_doc(naming_rule)
		naming_rule_2.prefix = "test-low-"
		naming_rule_2.priority = 0
		naming_rule_2.conditions = []
		naming_rule_2.insert()

		todo = frappe.get_doc(
			doctype="ToDo", priority="High", description="Is this my name " + frappe.generate_hash()
		).insert()

		todo_1 = frappe.get_doc(
			doctype="ToDo", priority="Medium", description="Is this my name " + frappe.generate_hash()
		).insert()

		todo_2 = frappe.get_doc(
			doctype="ToDo", priority="Low", description="Is this my name " + frappe.generate_hash()
		).insert()

		try:
			self.assertEqual(todo.name, "test-high-00001")
			self.assertEqual(todo_1.name, "test-medium-00001")
			self.assertEqual(todo_2.name, "test-low-00001")
		finally:
			naming_rule.delete()
			naming_rule_1.delete()
			naming_rule_2.delete()
			todo.delete()
			todo_1.delete()
			todo_2.delete()

	def test_counter_is_scoped_to_the_resolved_prefix(self):
		naming_rule = frappe.get_doc(
			doctype="Document Naming Rule",
			document_type="ToDo",
			prefix="test-prio-.priority.-",
			prefix_digits=5,
		).insert()
		self.addCleanup(naming_rule.delete)

		names = [self.make_todo(priority).name for priority in ("High", "Medium", "High")]

		self.assertEqual(names, ["test-prio-High-00001", "test-prio-Medium-00001", "test-prio-High-00002"])

	def test_series_key_is_the_resolved_prefix(self):
		naming_rule = frappe.get_doc(
			doctype="Document Naming Rule",
			document_type="ToDo",
			prefix="test-yearly-.YYYY.-",
			prefix_digits=5,
		).insert()
		self.addCleanup(naming_rule.delete)

		todo = self.make_todo()

		self.assertRegex(todo.name, r"^test-yearly-\d{4}-00001$")
		self.assertEqual(self.series_current(todo.name[:-5]), 1)

	def test_patch_seeds_series_from_existing_names(self):
		naming_rule = frappe.get_doc(
			doctype="Document Naming Rule",
			document_type="ToDo",
			prefix="test-seed-.YYYY.-",
			prefix_digits=5,
		).insert()
		self.addCleanup(naming_rule.delete)

		for _ in range(3):
			prefix = self.make_todo().name[:-5]

		series = DocType("Series")
		frappe.qb.from_(series).delete().where(series.name == prefix).run()

		seed_series_for_rule(frappe._dict(document_type="ToDo", prefix=naming_rule.prefix, prefix_digits=5))

		self.assertEqual(self.series_current(prefix), 3)
		self.assertEqual(self.make_todo().name, prefix + "00004")

	def test_patch_seeds_a_name_with_an_empty_prefix_part(self):
		naming_rule = self.make_rule("test-empty-.role.-")

		prefix = self.make_todo().name[:-5]
		self.assertEqual(prefix, "test-empty--")
		self.drop_series(prefix)

		seed_series_for_rule(frappe._dict(document_type="ToDo", prefix=naming_rule.prefix, prefix_digits=5))

		self.assertEqual(self.series_current(prefix), 1)

	def test_patch_seeds_disabled_rules(self):
		naming_rule = self.make_rule("test-disabled-")

		prefix = self.make_todo().name[:-5]
		naming_rule.disabled = 1
		naming_rule.save()
		self.drop_series(prefix)

		seed_naming_rule_series()

		self.assertEqual(self.series_current(prefix), 1)

	def make_rule(self, prefix):
		naming_rule = frappe.get_doc(
			doctype="Document Naming Rule",
			document_type="ToDo",
			prefix=prefix,
			prefix_digits=5,
		).insert()
		self.addCleanup(naming_rule.delete)
		return naming_rule

	def drop_series(self, prefix):
		series = DocType("Series")
		frappe.qb.from_(series).delete().where(series.name == prefix).run()

	def make_todo(self, priority="Medium"):
		todo = frappe.get_doc(
			doctype="ToDo",
			priority=priority,
			description="Is this my name " + frappe.generate_hash(),
		).insert()
		self.addCleanup(todo.delete)
		return todo

	def series_current(self, prefix):
		series = DocType("Series")
		row = frappe.qb.from_(series).where(series.name == prefix).select("current").run()
		return row[0][0] if row else None
