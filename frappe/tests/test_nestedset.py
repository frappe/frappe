# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.desk.treeview import get_children
from frappe.query_builder import Field
from frappe.query_builder.functions import Max
from frappe.tests import IntegrationTestCase
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

TEST_DOCTYPE = "Test Tree DocType"


class NestedSetTestUtil:
	def setup_test_doctype(self):
		frappe.db.delete("DocType", TEST_DOCTYPE)
		frappe.db.sql_ddl(f"drop table if exists `tab{TEST_DOCTYPE}`")

		self.tree_doctype = new_doctype(TEST_DOCTYPE, is_tree=True, autoname="field:some_fieldname")
		self.tree_doctype.insert()

		for record in records:
			d = frappe.new_doc(TEST_DOCTYPE)
			d.update(record)
			d.insert()

	def teardown_test_doctype(self):
		self.tree_doctype.delete()
		frappe.db.sql_ddl(f"drop table if exists `{TEST_DOCTYPE}`")

	def move_it_back(self):
		parent_1 = frappe.get_doc(TEST_DOCTYPE, "Parent 1")
		parent_1.parent_test_tree_doctype = "Root Node"
		parent_1.save()

	def get_no_of_children(self, record_name: str) -> int:
		if not record_name:
			return frappe.db.count(TEST_DOCTYPE)
		return len(get_descendants_of(TEST_DOCTYPE, record_name, ignore_permissions=True))


class TestNestedSet(IntegrationTestCase):
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
		max_rgt = frappe.qb.from_(TEST_DOCTYPE).select(Max(Field("rgt"))).run(pluck=True)[0]

		for record in records:
			lft, rgt, parent_test_tree_doctype = frappe.db.get_value(
				TEST_DOCTYPE,
				record["some_fieldname"],
				["lft", "rgt", "parent_test_tree_doctype"],
			)

			if parent_test_tree_doctype:
				parent_lft, parent_rgt = frappe.db.get_value(
					TEST_DOCTYPE, parent_test_tree_doctype, ["lft", "rgt"]
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
		leaf_node = frappe.get_doc(TEST_DOCTYPE, {"some_fieldname": "Parent 2"})
		leaf_node.parent_test_tree_doctype = "Child 3"
		self.assertRaises(NestedSetRecursionError, leaf_node.save)
		leaf_node.reload()

	def test_rebuild_tree(self):
		rebuild_tree(TEST_DOCTYPE)
		self.test_basic_tree()

	def test_move_group_into_another(self):
		old_lft, old_rgt = frappe.db.get_value(TEST_DOCTYPE, "Parent 2", ["lft", "rgt"])

		parent_1 = frappe.get_doc(TEST_DOCTYPE, "Parent 1")
		lft, rgt = parent_1.lft, parent_1.rgt

		parent_1.parent_test_tree_doctype = "Parent 2"
		parent_1.save()
		self.test_basic_tree()

		# after move
		new_lft, new_rgt = frappe.db.get_value(TEST_DOCTYPE, "Parent 2", ["lft", "rgt"])

		# lft should reduce
		self.assertEqual(old_lft - new_lft, rgt - lft + 1)

		# adjacent siblings, hence rgt diff will be 0
		self.assertEqual(new_rgt - old_rgt, 0)

		self.nsu.move_it_back()
		self.test_basic_tree()

	def test_move_leaf_into_another_group(self):
		child_2 = frappe.get_doc(TEST_DOCTYPE, "Child 2")

		# assert that child 2 is not already under parent 1
		parent_lft_old, parent_rgt_old = frappe.db.get_value(TEST_DOCTYPE, "Parent 2", ["lft", "rgt"])
		self.assertTrue((parent_lft_old > child_2.lft) and (parent_rgt_old > child_2.rgt))

		child_2.parent_test_tree_doctype = "Parent 2"
		child_2.save()
		self.test_basic_tree()

		# assert that child 2 is under parent 1
		parent_lft_new, parent_rgt_new = frappe.db.get_value(TEST_DOCTYPE, "Parent 2", ["lft", "rgt"])
		self.assertFalse((parent_lft_new > child_2.lft) and (parent_rgt_new > child_2.rgt))

	def test_delete_leaf(self):
		global records
		el = {"some_fieldname": "Child 1", "parent_test_tree_doctype": "Parent 1", "is_group": 0}

		child_1 = frappe.get_doc(TEST_DOCTYPE, "Child 1")
		child_1.delete()
		records.remove(el)

		self.test_basic_tree()

		n = frappe.new_doc(TEST_DOCTYPE)
		n.update(el)
		n.insert()
		records.append(el)

		self.test_basic_tree()

	def test_delete_group(self):
		# cannot delete group with child, but can delete leaf
		with self.assertRaises(NestedSetChildExistsError):
			frappe.delete_doc(TEST_DOCTYPE, "Parent 1")

	def test_remove_subtree(self):
		remove_subtree(TEST_DOCTYPE, "Parent 2")
		self.test_basic_tree()

	def test_rename_nestedset(self):
		doctype = new_doctype(is_tree=True).insert()

		# Rename doctype
		frappe.rename_doc("DocType", doctype.name, "Test " + random_string(10), force=True)

	def test_merge_groups(self):
		global records
		el = {"some_fieldname": "Parent 2", "parent_test_tree_doctype": "Root Node", "is_group": 1}
		frappe.rename_doc(TEST_DOCTYPE, "Parent 2", "Parent 1", merge=True)
		records.remove(el)
		self.test_basic_tree()

	def test_merge_leaves(self):
		global records
		el = {"some_fieldname": "Child 3", "parent_test_tree_doctype": "Parent 2", "is_group": 0}

		frappe.rename_doc(
			TEST_DOCTYPE,
			"Child 3",
			"Child 2",
			merge=True,
		)
		records.remove(el)
		self.test_basic_tree()

	def test_merge_leaf_into_group(self):
		with self.assertRaises(NestedSetInvalidMergeError):
			frappe.rename_doc(TEST_DOCTYPE, "Child 1", "Parent 1", merge=True)

	def test_merge_group_into_leaf(self):
		with self.assertRaises(NestedSetInvalidMergeError):
			frappe.rename_doc(TEST_DOCTYPE, "Parent 1", "Child 1", merge=True)

	def test_root_deletion(self):
		for doc in ["Child 3", "Child 2", "Child 1", "Parent 2", "Parent 1"]:
			frappe.delete_doc(TEST_DOCTYPE, doc)

		root_node = frappe.get_doc(TEST_DOCTYPE, "Root Node")

		# root deletion with allow_root_deletion
		# patched as delete_doc create a new instance of Root Node (using get_doc)
		root_node.allow_root_deletion = False
		with patch("frappe.get_doc", return_value=root_node):
			with self.assertRaises(frappe.ValidationError):
				root_node.delete()

		# root deletion without allow_root_deletion
		root_node.delete()
		self.assertFalse(frappe.db.exists(TEST_DOCTYPE, "Root Node"))

	def test_desc_filters(self):
		linked_doctype = (
			new_doctype(
				fields=[
					{
						"fieldname": "link_field",
						"fieldtype": "Link",
						"options": TEST_DOCTYPE,
					}
				]
			)
			.insert()
			.name
		)

		record = "Child 1"

		exclusive_filter = {"name": ("descendants of", record)}
		inclusive_filter = {"name": ("descendants of (inclusive)", record)}
		exclusive_link = {"link_field": ("descendants of", record)}
		inclusive_link = {"link_field": ("descendants of (inclusive)", record)}

		# db_query
		self.assertNotIn(record, frappe.get_all(TEST_DOCTYPE, exclusive_filter, run=0))
		self.assertIn(record, frappe.get_all(TEST_DOCTYPE, inclusive_filter, run=0))
		self.assertNotIn(record, frappe.get_all(linked_doctype, exclusive_link, run=0))
		self.assertIn(record, frappe.get_all(linked_doctype, inclusive_link, run=0))

		# QB
		self.assertNotIn(record, str(frappe.qb.get_query(TEST_DOCTYPE, filters=exclusive_filter)))
		self.assertIn(record, str(frappe.qb.get_query(TEST_DOCTYPE, filters=inclusive_filter)))

		self.assertNotIn(record, str(frappe.qb.get_query(table=linked_doctype, filters=exclusive_link)))
		self.assertIn(record, str(frappe.qb.get_query(table=linked_doctype, filters=inclusive_link)))

	def test_disabled_records_in_treeview(self):
		"""
		Tests the `get_children` util for showing / skipping disabled records in treeview
		"""
		doctype = (
			new_doctype(
				fields=[
					{
						"label": "Some Field",
						"fieldname": "some_fieldname",
						"fieldtype": "Data",
					},
					{
						"label": "Disabled",
						"fieldname": "disabled",
						"fieldtype": "Check",
					},
				],
				is_tree=True,
				autoname="field:some_fieldname",
			)
			.insert()
			.name
		)

		for record in [
			{"some_fieldname": "Root", "disabled": 0, "is_group": 1},
			{"some_fieldname": "Sub Tree 1", "disabled": 1, "parent_" + doctype: "Root", "is_group": 0},
		]:
			d = frappe.new_doc(doctype)
			d.update(record)
			d.insert()

		# Check if all records are fetched when flag is set to True
		self.assertEqual(len(get_children(doctype, include_disabled=True)), 2)

		# Check if disabled records are skipped is set to False
		# Children of disabled records are automatically skipped in recursion
		self.assertEqual(len(get_children(doctype)), 1)
