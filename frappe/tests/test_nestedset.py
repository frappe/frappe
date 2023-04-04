# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.query_builder import Field
from frappe.query_builder.functions import Max
from frappe.tests.utils import FrappeTestCase
from frappe.utils import random_string
from frappe.utils.nestedset import (
	NestedSetChildExistsError,
	NestedSetInvalidMergeError,
	NestedSetRecursionError,
	get_descendants_of,
	rebuild_tree,
	remove_subtree,
)

records = [
	{
		"some_fieldname": "Root Node",
		"parent_test_tree_doctype": None,
		"is_group": 1,
	},
	{
		"some_fieldname": "Parent 1",
		"parent_test_tree_doctype": "Root Node",
		"is_group": 1,
	},
	{
		"some_fieldname": "Parent 2",
		"parent_test_tree_doctype": "Root Node",
		"is_group": 1,
	},
	{
		"some_fieldname": "Child 1",
		"parent_test_tree_doctype": "Parent 1",
		"is_group": 0,
	},
	{
		"some_fieldname": "Child 2",
		"parent_test_tree_doctype": "Parent 1",
		"is_group": 0,
	},
	{
		"some_fieldname": "Child 3",
		"parent_test_tree_doctype": "Parent 2",
		"is_group": 0,
	},
]


class NestedSetTestUtil:
	def setup_test_doctype(self):
		frappe.db.sql("delete from `tabDocType` where `name` = 'Test Tree DocType'")
		frappe.db.sql_ddl("drop table if exists `tabTest Tree DocType`")

		self.tree_doctype = new_doctype(
			"Test Tree DocType", is_tree=True, autoname="field:some_fieldname"
		)
		self.tree_doctype.insert()

		for record in records:
			d = frappe.new_doc("Test Tree DocType")
			d.update(record)
			d.insert()

	def teardown_test_doctype(self):
		self.tree_doctype.delete()
		frappe.db.sql_ddl("drop table if exists `tabTest Tree DocType`")

	def move_it_back(self):
		parent_1 = frappe.get_doc("Test Tree DocType", "Parent 1")
		parent_1.parent_test_tree_doctype = "Root Node"
		parent_1.save()

	def get_no_of_children(self, record_name: str) -> int:
		if not record_name:
			return frappe.db.count("Test Tree DocType")
		return len(get_descendants_of("Test Tree DocType", record_name, ignore_permissions=True))


class TestNestedSet(FrappeTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		cls.nsu = NestedSetTestUtil()
		cls.nsu.setup_test_doctype()
		super().setUpClass()

	@classmethod
	def tearDownClass(cls) -> None:
		cls.nsu.teardown_test_doctype()
		super().tearDownClass()

	def setUp(self) -> None:
		frappe.db.rollback()

	def test_basic_tree(self):
		global records

		min_lft = 1
		max_rgt = frappe.qb.from_("Test Tree DocType").select(Max(Field("rgt"))).run(pluck=True)[0]

		for record in records:
			lft, rgt, parent_test_tree_doctype = frappe.db.get_value(
				"Test Tree DocType",
				record["some_fieldname"],
				["lft", "rgt", "parent_test_tree_doctype"],
			)

			if parent_test_tree_doctype:
				parent_lft, parent_rgt = frappe.db.get_value(
					"Test Tree DocType", parent_test_tree_doctype, ["lft", "rgt"]
				)
			else:
				# root
				parent_lft = min_lft - 1
				parent_rgt = max_rgt + 1

			self.assertTrue(lft)
			self.assertTrue(rgt)
			self.assertTrue(lft < rgt)
			self.assertTrue(parent_lft < parent_rgt)
			self.assertTrue(lft > parent_lft)
			self.assertTrue(rgt < parent_rgt)
			self.assertTrue(lft >= min_lft)
			self.assertTrue(rgt <= max_rgt)

			no_of_children = self.nsu.get_no_of_children(record["some_fieldname"])
			self.assertTrue(
				rgt == (lft + 1 + (2 * no_of_children)),
				msg=(record, no_of_children, self.nsu.get_no_of_children(record["some_fieldname"])),
			)

			no_of_children = self.nsu.get_no_of_children(parent_test_tree_doctype)
			self.assertTrue(parent_rgt == (parent_lft + 1 + (2 * no_of_children)))

	def test_recursion(self):
		leaf_node = frappe.get_doc("Test Tree DocType", {"some_fieldname": "Parent 2"})
		leaf_node.parent_test_tree_doctype = "Child 3"
		self.assertRaises(NestedSetRecursionError, leaf_node.save)
		leaf_node.reload()

	def test_rebuild_tree(self):
		rebuild_tree("Test Tree DocType", "parent_test_tree_doctype")
		self.test_basic_tree()

	def test_move_group_into_another(self):
		old_lft, old_rgt = frappe.db.get_value("Test Tree DocType", "Parent 2", ["lft", "rgt"])

		parent_1 = frappe.get_doc("Test Tree DocType", "Parent 1")
		lft, rgt = parent_1.lft, parent_1.rgt

		parent_1.parent_test_tree_doctype = "Parent 2"
		parent_1.save()
		self.test_basic_tree()

		# after move
		new_lft, new_rgt = frappe.db.get_value("Test Tree DocType", "Parent 2", ["lft", "rgt"])

		# lft should reduce
		self.assertEqual(old_lft - new_lft, rgt - lft + 1)

		# adjacent siblings, hence rgt diff will be 0
		self.assertEqual(new_rgt - old_rgt, 0)

		self.nsu.move_it_back()
		self.test_basic_tree()

	def test_move_leaf_into_another_group(self):
		child_2 = frappe.get_doc("Test Tree DocType", "Child 2")

		# assert that child 2 is not already under parent 1
		parent_lft_old, parent_rgt_old = frappe.db.get_value(
			"Test Tree DocType", "Parent 2", ["lft", "rgt"]
		)
		self.assertTrue((parent_lft_old > child_2.lft) and (parent_rgt_old > child_2.rgt))

		child_2.parent_test_tree_doctype = "Parent 2"
		child_2.save()
		self.test_basic_tree()

		# assert that child 2 is under parent 1
		parent_lft_new, parent_rgt_new = frappe.db.get_value(
			"Test Tree DocType", "Parent 2", ["lft", "rgt"]
		)
		self.assertFalse((parent_lft_new > child_2.lft) and (parent_rgt_new > child_2.rgt))

	def test_delete_leaf(self):
		global records
		el = {"some_fieldname": "Child 1", "parent_test_tree_doctype": "Parent 1", "is_group": 0}

		child_1 = frappe.get_doc("Test Tree DocType", "Child 1")
		child_1.delete()
		records.remove(el)

		self.test_basic_tree()

		n = frappe.new_doc("Test Tree DocType")
		n.update(el)
		n.insert()
		records.append(el)

		self.test_basic_tree()

	def test_delete_group(self):
		# cannot delete group with child, but can delete leaf
		with self.assertRaises(NestedSetChildExistsError):
			frappe.delete_doc("Test Tree DocType", "Parent 1")

	def test_remove_subtree(self):
		remove_subtree("Test Tree DocType", "Parent 2")
		self.test_basic_tree()

	def test_rename_nestedset(self):
		doctype = new_doctype(is_tree=True).insert()

		# Rename doctype
		frappe.rename_doc("DocType", doctype.name, "Test " + random_string(10), force=True)

	def test_merge_groups(self):
		global records
		el = {"some_fieldname": "Parent 2", "parent_test_tree_doctype": "Root Node", "is_group": 1}
		frappe.rename_doc("Test Tree DocType", "Parent 2", "Parent 1", merge=True)
		records.remove(el)
		self.test_basic_tree()

	def test_merge_leaves(self):
		global records
		el = {"some_fieldname": "Child 3", "parent_test_tree_doctype": "Parent 2", "is_group": 0}

		frappe.rename_doc(
			"Test Tree DocType",
			"Child 3",
			"Child 2",
			merge=True,
		)
		records.remove(el)
		self.test_basic_tree()

	def test_merge_leaf_into_group(self):
		with self.assertRaises(NestedSetInvalidMergeError):
			frappe.rename_doc("Test Tree DocType", "Child 1", "Parent 1", merge=True)

	def test_merge_group_into_leaf(self):
		with self.assertRaises(NestedSetInvalidMergeError):
			frappe.rename_doc("Test Tree DocType", "Parent 1", "Child 1", merge=True)
