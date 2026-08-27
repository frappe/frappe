import random
import string
from unittest.mock import patch

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.database import savepoint
from frappe.desk.form import linked_with
from frappe.tests import IntegrationTestCase


def hard_delete_referencing_child2_records(doc, method=None):
	"""Mimic a voucher on_trash that removes its submitted ledger rows."""
	frappe.db.delete("Child DocType2", {"child_doctype1": doc.name})


def block_cancel_while_child2_submitted(doc, method=None):
	"""Mimic a controller that wants referencing documents cancelled first."""
	if frappe.db.exists("Child DocType2", {"child_doctype1": doc.name, "docstatus": 1}):
		frappe.throw(frappe._("Cancel the referencing document first"))


class TestLinkedWith(IntegrationTestCase):
	def setUp(self):
		parent_doctype = new_doctype("Parent DocType")
		parent_doctype.is_submittable = 1
		parent_doctype.insert()

		child_doctype1 = new_doctype(
			"Child DocType1",
			fields=[
				{
					"label": "Parent DocType",
					"fieldname": "parent_doctype",
					"fieldtype": "Link",
					"options": "Parent DocType",
				},
				{
					"label": "Reference field",
					"fieldname": "reference_name",
					"fieldtype": "Dynamic Link",
					"options": "reference_doctype",
				},
				{
					"label": "Reference Doctype",
					"fieldname": "reference_doctype",
					"fieldtype": "Link",
					"options": "DocType",
				},
			],
			unique=0,
		)
		child_doctype1.is_submittable = 1
		child_doctype1.insert()

		child_doctype2 = new_doctype(
			"Child DocType2",
			fields=[
				{
					"label": "Parent DocType",
					"fieldname": "parent_doctype",
					"fieldtype": "Link",
					"options": "Parent DocType",
				},
				{
					"label": "Child DocType1",
					"fieldname": "child_doctype1",
					"fieldtype": "Link",
					"options": "Child DocType1",
				},
			],
			unique=0,
		)
		child_doctype2.is_submittable = 1
		child_doctype2.insert()

	def tearDown(self):
		for doctype in ["Parent DocType", "Child DocType1", "Child DocType2"]:
			frappe.delete_doc("DocType", doctype)
			frappe.db.commit()

	def test_get_doctype_references_by_link_field(self):
		references = linked_with.get_references_across_doctypes_by_link_field(to_doctypes=["Parent DocType"])
		self.assertEqual(len(references["Parent DocType"]), 3)
		self.assertIn(
			{"doctype": "Child DocType1", "fieldname": "parent_doctype"}, references["Parent DocType"]
		)
		self.assertIn(
			{"doctype": "Child DocType2", "fieldname": "parent_doctype"}, references["Parent DocType"]
		)

		references = linked_with.get_references_across_doctypes_by_link_field(to_doctypes=["Child DocType1"])
		self.assertEqual(len(references["Child DocType1"]), 2)
		self.assertIn(
			{"doctype": "Child DocType2", "fieldname": "child_doctype1"}, references["Child DocType1"]
		)

		references = linked_with.get_references_across_doctypes_by_link_field(
			to_doctypes=["Child DocType1", "Parent DocType"], limit_link_doctypes=["Child DocType1"]
		)
		self.assertEqual(len(references["Child DocType1"]), 1)
		self.assertEqual(len(references["Parent DocType"]), 1)
		self.assertIn(
			{"doctype": "Child DocType1", "fieldname": "parent_doctype"}, references["Parent DocType"]
		)

	def test_get_doctype_references_by_dlink_field(self):
		references = linked_with.get_references_across_doctypes_by_dynamic_link_field(
			to_doctypes=["Parent DocType"],
			limit_link_doctypes=["Parent DocType", "Child DocType1", "Child DocType2"],
		)
		self.assertFalse(references)

		parent_record = frappe.get_doc({"doctype": "Parent DocType"}).insert()

		child_record = frappe.get_doc(
			{
				"doctype": "Child DocType1",
				"reference_doctype": "Parent DocType",
				"reference_name": parent_record.name,
			}
		).insert()

		references = linked_with.get_references_across_doctypes_by_dynamic_link_field(
			to_doctypes=["Parent DocType"],
			limit_link_doctypes=["Parent DocType", "Child DocType1", "Child DocType2"],
		)

		self.assertEqual(len(references["Parent DocType"]), 1)
		self.assertEqual(references["Parent DocType"][0]["doctype"], "Child DocType1")
		self.assertEqual(references["Parent DocType"][0]["doctype_fieldname"], "reference_doctype")

		child_record.delete()
		parent_record.delete()

	def test_get_submitted_linked_docs(self):
		parent_record = frappe.get_doc({"doctype": "Parent DocType"}).insert()

		child_record = frappe.get_doc(
			{
				"doctype": "Child DocType1",
				"reference_doctype": "Parent DocType",
				"reference_name": parent_record.name,
				"docstatus": 1,
			}
		).insert()

		linked_docs = linked_with.get_submitted_linked_docs(parent_record.doctype, parent_record.name)["docs"]
		self.assertIn(child_record.name, linked_docs[0]["name"])
		child_record.cancel()
		child_record.delete()
		parent_record.delete()

	def test_cancel_all_linked_docs_accepts_native(self):
		doc = frappe.get_doc({"doctype": "Parent DocType"}).insert()
		doc.submit()

		# docs as a native list of dicts and ignore_doctypes as a native list (JSON request body)
		linked_with.cancel_all_linked_docs(
			docs=[{"doctype": "Parent DocType", "name": doc.name, "docstatus": 1}],
			ignore_doctypes_on_cancel_all=["Comment"],
		)
		self.assertEqual(frappe.db.get_value("Parent DocType", doc.name, "docstatus"), 2)
		doc.reload().delete()

	def test_get_submitted_linked_docs_deepest_first(self):
		parent = frappe.get_doc({"doctype": "Parent DocType"}).insert().submit()
		child1 = (
			frappe.get_doc({"doctype": "Child DocType1", "parent_doctype": parent.name}).insert().submit()
		)
		child2 = (
			frappe.get_doc({"doctype": "Child DocType2", "child_doctype1": child1.name}).insert().submit()
		)

		docs = linked_with.get_submitted_linked_docs(parent.doctype, parent.name)["docs"]

		# child2 references child1, so it must come first to be cancellable in list order
		self.assertEqual([doc["name"] for doc in docs], [child2.name, child1.name])

	def test_get_submitted_linked_docs_has_no_duplicates(self):
		parent = frappe.get_doc({"doctype": "Parent DocType"}).insert().submit()
		child1 = (
			frappe.get_doc({"doctype": "Child DocType1", "parent_doctype": parent.name}).insert().submit()
		)
		frappe.get_doc(
			{"doctype": "Child DocType2", "parent_doctype": parent.name, "child_doctype1": child1.name}
		).insert().submit()

		result = linked_with.get_submitted_linked_docs(parent.doctype, parent.name)

		keys = [(doc["doctype"], doc["name"]) for doc in result["docs"]]
		self.assertEqual(len(keys), len(set(keys)))
		self.assertEqual(result["count"], 2)

	def test_cancel_all_linked_docs_defers_blocked_docs(self):
		parent = frappe.get_doc({"doctype": "Parent DocType"}).insert().submit()
		child1 = (
			frappe.get_doc({"doctype": "Child DocType1", "parent_doctype": parent.name}).insert().submit()
		)
		child2 = (
			frappe.get_doc(
				{"doctype": "Child DocType2", "parent_doctype": parent.name, "child_doctype1": child1.name}
			)
			.insert()
			.submit()
		)

		# child1 is blocked by child2 and passed first (with a duplicate); it must
		# get deferred and cancelled on a later pass instead of failing
		message_count = len(frappe.local.message_log)
		linked_with.cancel_all_linked_docs(
			docs=[
				{"doctype": "Child DocType1", "name": child1.name, "docstatus": 1},
				{"doctype": "Child DocType1", "name": child1.name, "docstatus": 1},
				{"doctype": "Child DocType2", "name": child2.name, "docstatus": 1},
			]
		)

		self.assertTrue(child1.reload().docstatus.is_cancelled())
		self.assertTrue(child2.reload().docstatus.is_cancelled())
		# the link error of the deferred attempt must not leak to the user
		self.assertEqual(len(frappe.local.message_log), message_count)

	def test_deferred_attempts_drop_queued_commit_hooks(self):
		"""A rolled-back attempt must not leave its commit or rollback hooks
		queued, or a later commit or rollback runs side effects of work that
		never happened."""
		attempts = []

		def process(docinfo):
			frappe.db.after_commit.add(lambda: None)
			frappe.db.after_rollback.add(lambda: None)
			attempts.append(docinfo["name"])
			if docinfo["name"] == "blocked" and attempts.count("blocked") == 1:
				raise frappe.LinkExistsError

		after_commit_count = len(frappe.db.after_commit)
		after_rollback_count = len(frappe.db.after_rollback)
		linked_with.process_linked_docs_in_dependency_order(
			[
				{"doctype": "Parent DocType", "name": "blocked"},
				{"doctype": "Parent DocType", "name": "free"},
			],
			process,
			"Processing",
		)

		# three attempts, two successful: only their hooks survive
		self.assertEqual(attempts, ["blocked", "free", "blocked"])
		self.assertEqual(len(frappe.db.after_commit), after_commit_count + 2)
		self.assertEqual(len(frappe.db.after_rollback), after_rollback_count + 2)

	def test_deferred_attempts_drop_queued_realtime_events(self):
		"""Realtime events queued by a rolled-back attempt must not stay in the
		log that gets flushed on commit."""
		attempts = []

		def process(docinfo):
			attempts.append(docinfo["name"])
			frappe.publish_realtime(
				"test_dependency_order",
				{"attempt": len(attempts)},
				user=frappe.session.user,
				after_commit=True,
			)
			if docinfo["name"] == "blocked" and attempts.count("blocked") == 1:
				raise frappe.LinkExistsError

		linked_with.process_linked_docs_in_dependency_order(
			[
				{"doctype": "Parent DocType", "name": "blocked"},
				{"doctype": "Parent DocType", "name": "free"},
			],
			process,
			"Processing",
		)

		events = [
			message for event, message, room in frappe.local._realtime_log if event == "test_dependency_order"
		]
		# only the events of the two successful attempts survive
		self.assertEqual(events, [{"attempt": 2}, {"attempt": 3}])

	def test_deferred_attempts_run_their_rollback_callbacks(self):
		"""A rolled-back attempt's rollback watchers must run, or the effects they
		compensate for (files written, caches primed) stay behind."""
		compensated = []
		attempts = []

		def process(docinfo):
			attempts.append(docinfo["name"])
			if docinfo["name"] == "blocked" and attempts.count("blocked") == 1:
				frappe.db.after_rollback.add(lambda: compensated.append("blocked"))
				raise frappe.LinkExistsError

		after_rollback_count = len(frappe.db.after_rollback)
		linked_with.process_linked_docs_in_dependency_order(
			[
				{"doctype": "Parent DocType", "name": "blocked"},
				{"doctype": "Parent DocType", "name": "free"},
			],
			process,
			"Processing",
		)

		self.assertEqual(compensated, ["blocked"])
		self.assertEqual(len(frappe.db.after_rollback), after_rollback_count)

	def test_deferred_attempts_restore_currently_saving(self):
		"""Document saves append to frappe.flags.currently_saving and pop only on
		success, so a deferred failure must not leak its entry."""
		attempts = []

		def process(docinfo):
			attempts.append(docinfo["name"])
			frappe.flags.currently_saving.append(("Parent DocType", docinfo["name"]))
			if docinfo["name"] == "blocked" and attempts.count("blocked") == 1:
				raise frappe.LinkExistsError
			frappe.flags.currently_saving.remove(("Parent DocType", docinfo["name"]))

		before = list(frappe.flags.currently_saving)
		linked_with.process_linked_docs_in_dependency_order(
			[
				{"doctype": "Parent DocType", "name": "blocked"},
				{"doctype": "Parent DocType", "name": "free"},
			],
			process,
			"Processing",
		)

		self.assertEqual(list(frappe.flags.currently_saving), before)

	def test_deferred_attempts_restore_replaced_message_log(self):
		"""Some permission checks swap the message log out and do not put it back
		when they raise; the snapshot must survive the replacement."""
		original = frappe.local.message_log
		frappe.local.message_log = ["kept"]
		attempts = []

		def process(docinfo):
			attempts.append(docinfo["name"])
			if docinfo["name"] == "blocked" and attempts.count("blocked") == 1:
				frappe.local.message_log = ["from the failed attempt"]
				raise frappe.LinkExistsError

		try:
			linked_with.process_linked_docs_in_dependency_order(
				[
					{"doctype": "Parent DocType", "name": "blocked"},
					{"doctype": "Parent DocType", "name": "free"},
				],
				process,
				"Processing",
			)
			self.assertEqual(frappe.local.message_log, ["kept"])
		finally:
			frappe.local.message_log = original

	def test_cancel_all_linked_docs_defers_controller_blocked_docs(self):
		"""A controller check that wants a referencing document cancelled first
		raises a plain ValidationError; the document must get deferred, not fail
		the run."""
		child1 = frappe.get_doc({"doctype": "Child DocType1"}).insert().submit()
		child2 = (
			frappe.get_doc({"doctype": "Child DocType2", "child_doctype1": child1.name}).insert().submit()
		)

		hook = f"{__name__}.block_cancel_while_child2_submitted"
		self.addCleanup(setattr, frappe.local, "doc_events_hooks", None)
		with self.patch_hooks({"doc_events": {"Child DocType1": {"before_cancel": [hook]}}}):
			frappe.local.doc_events_hooks = None
			linked_with.cancel_all_linked_docs(
				docs=[
					{"doctype": "Child DocType1", "name": child1.name, "docstatus": 1},
					{"doctype": "Child DocType2", "name": child2.name, "docstatus": 1},
				]
			)

		self.assertTrue(child1.reload().docstatus.is_cancelled())
		self.assertTrue(child2.reload().docstatus.is_cancelled())

	def test_get_linked_docs_to_delete_deepest_first(self):
		parent = frappe.get_doc({"doctype": "Parent DocType"}).insert()
		child1 = frappe.get_doc({"doctype": "Child DocType1", "parent_doctype": parent.name}).insert()
		child2 = frappe.get_doc({"doctype": "Child DocType2", "child_doctype1": child1.name}).insert()

		docs = linked_with.get_linked_docs_to_delete(parent.doctype, parent.name)["docs"]

		# child2 references child1, so it must come first to be deletable in list order
		self.assertEqual([doc["name"] for doc in docs], [child2.name, child1.name])

	def test_get_linked_docs_to_delete_excludes_unreadable_docs(self):
		"""Linked documents the user cannot read must stay hidden from the listing."""
		from frappe.permissions import add_permission

		parent = frappe.get_doc({"doctype": "Parent DocType"}).insert()
		child1 = frappe.get_doc({"doctype": "Child DocType1", "parent_doctype": parent.name}).insert()
		frappe.get_doc({"doctype": "Child DocType2", "parent_doctype": parent.name}).insert()

		add_permission("Parent DocType", "All")
		add_permission("Child DocType1", "All")

		with self.set_user("test1@example.com"):
			docs = linked_with.get_linked_docs_to_delete(parent.doctype, parent.name)["docs"]

		self.assertEqual(docs, [{"doctype": "Child DocType1", "name": child1.name}])

	def test_get_linked_docs_to_delete_truncates_large_graphs(self):
		"""A graph larger than the cap returns no documents, so the caller falls
		back to a plain delete instead of walking everything."""
		parent = frappe.get_doc({"doctype": "Parent DocType"}).insert()
		frappe.get_doc({"doctype": "Child DocType1", "parent_doctype": parent.name}).insert()

		with patch.object(linked_with, "MAX_LINKED_DELETE_DOCUMENTS", 0):
			result = linked_with.get_linked_docs_to_delete(parent.doctype, parent.name)

		self.assertEqual(result, {"docs": [], "count": 0, "truncated": True})

	def test_delete_all_linked_docs_defers_blocked_docs(self):
		parent = frappe.get_doc({"doctype": "Parent DocType"}).insert()
		child1 = frappe.get_doc({"doctype": "Child DocType1", "parent_doctype": parent.name}).insert()
		child2 = frappe.get_doc(
			{"doctype": "Child DocType2", "parent_doctype": parent.name, "child_doctype1": child1.name}
		).insert()

		# child1 is blocked by child2 and passed first; it must get deferred
		# and deleted on a later pass instead of failing
		result = linked_with.delete_all_linked_docs(
			docs=[
				{"doctype": "Child DocType1", "name": child1.name},
				{"doctype": "Child DocType2", "name": child2.name},
			]
		)

		self.assertEqual(
			result,
			{
				"deleted": [
					{"doctype": "Child DocType1", "name": child1.name},
					{"doctype": "Child DocType2", "name": child2.name},
				],
				"skipped": [],
			},
		)
		self.assertFalse(frappe.db.exists("Child DocType1", child1.name))
		self.assertFalse(frappe.db.exists("Child DocType2", child2.name))
		parent.delete()

	def test_delete_all_linked_docs_waits_for_on_trash_cleanup(self):
		"""A submitted document that only an on_trash hook removes (like a ledger
		entry removed with its voucher) must get deferred, not fail the run."""
		child1 = frappe.get_doc({"doctype": "Child DocType1"}).insert()
		child2 = (
			frappe.get_doc({"doctype": "Child DocType2", "child_doctype1": child1.name}).insert().submit()
		)

		hook = f"{__name__}.hard_delete_referencing_child2_records"
		self.addCleanup(setattr, frappe.local, "doc_events_hooks", None)
		with self.patch_hooks({"doc_events": {"Child DocType1": {"on_trash": [hook]}}}):
			frappe.local.doc_events_hooks = None
			linked_with.delete_all_linked_docs(
				docs=[
					{"doctype": "Child DocType2", "name": child2.name},
					{"doctype": "Child DocType1", "name": child1.name},
				]
			)

		self.assertFalse(frappe.db.exists("Child DocType1", child1.name))
		self.assertFalse(frappe.db.exists("Child DocType2", child2.name))

	def test_delete_all_linked_docs_skips_undeletable_docs(self):
		"""A document that stays undeletable must get skipped and reported without
		undoing the deleted documents or leaking messages of failed attempts."""
		child1 = frappe.get_doc({"doctype": "Child DocType1"}).insert().submit()
		child2 = frappe.get_doc({"doctype": "Child DocType2"}).insert()
		message_count = len(frappe.local.message_log)

		result = linked_with.delete_all_linked_docs(
			docs=[
				{"doctype": "Child DocType1", "name": child1.name},
				{"doctype": "Child DocType2", "name": child2.name},
			]
		)

		self.assertEqual(result["deleted"], [{"doctype": "Child DocType2", "name": child2.name}])
		self.assertEqual(result["skipped"], [{"doctype": "Child DocType1", "name": child1.name}])
		self.assertTrue(frappe.db.exists("Child DocType1", child1.name))
		self.assertFalse(frappe.db.exists("Child DocType2", child2.name))
		self.assertEqual(len(frappe.local.message_log), message_count)
		child1.reload().cancel()

	def test_get_submitted_linked_docs_accepts_native_ignore_list(self):
		parent_record = frappe.get_doc({"doctype": "Parent DocType"}).insert()

		# ignore_doctypes_on_cancel_all as a native list (frappe.parse_json passthrough, L43)
		result = linked_with.get_submitted_linked_docs(
			parent_record.doctype, parent_record.name, ignore_doctypes_on_cancel_all=["Comment"]
		)
		self.assertIn("docs", result)
		parent_record.delete()

	def test_get_linked_docs_accepts_native_linkinfo(self):
		parent_record = frappe.get_doc({"doctype": "Parent DocType"}).insert()
		# linkinfo as a native dict instead of a JSON string (L429)
		out = linked_with.get_linked_docs(
			"Parent DocType", parent_record.name, linkinfo=linked_with.get_linked_doctypes("Parent DocType")
		)
		self.assertIsInstance(out, dict)
		parent_record.delete()

	def test_check_delete_integrity(self):
		"""Don't allow deleting cancelled document if amendment exists"""
		doc = frappe.get_doc({"doctype": "Parent DocType"}).insert()
		doc.submit()
		doc.cancel()

		amendment = frappe.copy_doc(doc)
		amendment.amended_from = doc.name
		amendment.docstatus = 0
		amendment.insert()
		amendment.submit()

		self.assertRaises(frappe.LinkExistsError, doc.delete)

	def test_virtual_child_table_excluded_from_linked_docs(self):
		"""A virtual istable doctype with a Link field has no real table, so it must be excluded
		from linked docs rather than resolved to its parent and queried."""
		target = new_doctype("Linked Target DocType", issingle=1)
		target.insert()

		virtual_child = new_doctype(
			"Virtual Linked Child",
			fields=[
				{
					"label": "Target Link",
					"fieldname": "target_link",
					"fieldtype": "Link",
					"options": "Linked Target DocType",
				}
			],
		)
		virtual_child.is_virtual = 1
		virtual_child.istable = 1
		virtual_child.insert()

		parent = new_doctype(
			"Virtual Child Parent",
			fields=[
				{
					"label": "Items",
					"fieldname": "items",
					"fieldtype": "Table",
					"options": "Virtual Linked Child",
					"is_virtual": 1,
				}
			],
			issingle=1,
		)
		parent.insert()

		try:
			linkinfo = linked_with.get_linked_doctypes("Linked Target DocType")

			# the virtual child must not survive as a top-level link or be buried as a parent's child_doctype
			self.assertNotIn("Virtual Linked Child", linkinfo)
			self.assertNotIn(
				"Virtual Linked Child", [info.get("child_doctype") for info in linkinfo.values()]
			)
		finally:
			for doctype in ("Virtual Child Parent", "Virtual Linked Child", "Linked Target DocType"):
				frappe.delete_doc("DocType", doctype)

	def test_reserved_keywords(self):
		dt_name = "Test " + "".join(random.sample(string.ascii_lowercase, 10))
		new_doctype(
			dt_name,
			fields=[
				{
					"fieldname": "from",
					"fieldtype": "Link",
					"options": "DocType",
				},
				{
					"fieldname": "order",
					"fieldtype": "Dynamic Link",
					"options": "from",
				},
			],
			is_submittable=True,
		).insert()

		linked_doc = frappe.new_doc(dt_name).insert().submit()

		second_doc = (
			frappe.new_doc(dt_name, **{"from": linked_doc.doctype, "order": linked_doc.name})
			.insert()
			.submit()
		)

		with savepoint(frappe.LinkExistsError):
			linked_doc.cancel() and self.fail("Cancellation shouldn't have worked")

		second_doc.cancel()
		linked_doc.reload().cancel()
