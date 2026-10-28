# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

"""Desk v1 gets the same output from shared code that desk v2 refactored.

Each case pins what the merge base of `develop` and `desk-v2` returns, and passes on both.
"""

import json
from functools import cached_property
from unittest.mock import patch

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.desk.form.assign_to import add as add_assignment
from frappe.desk.form.load import getdoc
from frappe.desk.reportview import get_count
from frappe.model.utils.user_settings import sync_user_settings, update_user_settings
from frappe.share import add as add_share
from frappe.tests import IntegrationTestCase
from frappe.tests.test_api import FrappeAPITestCase
from frappe.utils.file_manager import save_file

DESK_USER = "parity-desk-user@example.com"
WORKSPACE_MANAGER = "parity-workspace-manager@example.com"
DESK_PERMISSION = {"role": "Desk User", "read": 1, "write": 1, "create": 1, "share": 1}


class TestSidebarPermissionParity(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_user(DESK_USER, "Report Manager")
		make_user(WORKSPACE_MANAGER, "Workspace Manager")
		with patch.dict(frappe.flags, in_import=True):
			cls.rows = sorted(
				frappe.get_doc(doctype="Sidebar", title=f"Parity Sidebar {key}").insert().name for key in "AB"
			)

	def test_v1_rows_list_for_every_desk_user(self):
		for user in (DESK_USER, WORKSPACE_MANAGER):
			with self.set_user(user):
				rows = frappe.get_list("Sidebar", filters={"name": ("in", self.rows)}, pluck="name")
				self.assertEqual(sorted(rows), self.rows, user)
				for name in self.rows:
					self.assertTrue(frappe.has_permission("Sidebar", doc=name), (user, name))


class TestValidationErrorParity(FrappeAPITestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_user(DESK_USER, "Report Manager")
		cls.child = new_doctype(
			istable=1,
			fields=[
				{"fieldname": "row_label", "label": "Row Label", "fieldtype": "Data", "reqd": 1},
				{"fieldname": "row_user", "label": "Row User", "fieldtype": "Link", "options": "User"},
			],
		).insert()
		cls.parent = new_doctype(
			fields=[
				{"fieldname": "subject", "label": "Subject", "fieldtype": "Data", "reqd": 1},
				{"fieldname": "ref_user", "label": "Ref User", "fieldtype": "Link", "options": "User"},
				{"fieldname": "rows", "label": "Rows", "fieldtype": "Table", "options": cls.child.name},
			],
			permissions=[DESK_PERMISSION],
		).insert()
		frappe.db.commit()  # nosemgrep

	@classmethod
	def tearDownClass(cls):
		frappe.db.commit()  # nosemgrep
		cls.parent.delete()
		cls.child.delete()
		frappe.delete_doc_if_exists("User", DESK_USER, force=True)
		frappe.db.commit()  # nosemgrep
		super().tearDownClass()

	@cached_property
	def sid(self) -> str:
		from frappe.auth import CookieManager, LoginManager
		from frappe.utils import set_request

		with patch.object(frappe.local, "request", None, create=True), self.set_user("Administrator"):
			set_request(path="/")
			frappe.local.cookie_manager = CookieManager()
			frappe.local.login_manager = LoginManager()
			frappe.local.login_manager.login_as(DESK_USER)
			return frappe.session.sid

	def missing_values(self) -> dict:
		return {"doctype": self.parent.name, "rows": [{"row_user": DESK_USER}]}

	def bad_links(self) -> dict:
		return {
			"doctype": self.parent.name,
			"subject": "Parity",
			"ref_user": "nobody@example.com",
			"rows": [{"row_label": "One", "row_user": "ghost@example.com"}],
		}

	def mandatory_messages(self) -> list[str]:
		return [
			f"Error: Value missing for {self.parent.name}: Subject",
			f"Error: <strong>{self.child.name}</strong> Row #1: Value missing for: Row Label",
		]

	def test_mandatory_error_message(self):
		frappe.clear_messages()
		with self.set_user(DESK_USER), self.assertRaises(frappe.MandatoryError) as raised:
			doc = frappe.get_doc(self.missing_values())
			doc.insert()

		self.assertEqual(str(raised.exception), f"[{self.parent.name}, {doc.name}]: subject, row_label")
		self.assertEqual([m.message for m in frappe.message_log], self.mandatory_messages())

	def test_link_error_message(self):
		frappe.clear_messages()
		with self.set_user(DESK_USER), self.assertRaises(frappe.LinkValidationError) as raised:
			frappe.get_doc(self.bad_links()).insert()

		self.assertEqual(str(raised.exception), LINK_MESSAGE)
		self.assertEqual([m.message for m in frappe.message_log], [LINK_MESSAGE])

	def test_api_v1_error_response(self):
		cases = (
			(self.missing_values(), "MandatoryError", self.mandatory_messages()),
			(self.bad_links(), "LinkValidationError", [LINK_MESSAGE]),
		)
		for doc, exc_type, expected in cases:
			response = self.post(
				self.method("frappe.client.insert"), {"sid": self.sid, "doc": json.dumps(doc)}
			)
			self.assertEqual(response.status_code, 417, exc_type)
			self.assertEqual(set(response.json) - TRACEBACK_KEYS, {"exc_type", "_server_messages"}, exc_type)
			self.assertEqual(response.json["exc_type"], exc_type)
			sent = [json.loads(m)["message"] for m in json.loads(response.json["_server_messages"])]
			self.assertEqual(sent, expected)


class TestDocinfoParity(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_user(DESK_USER, "Report Manager")
		make_user(WORKSPACE_MANAGER, "Workspace Manager")
		cls.doctype = new_doctype(
			track_changes=1,
			track_views=1,
			fields=[{"fieldname": "subject", "label": "Subject", "fieldtype": "Data"}],
			permissions=[DESK_PERMISSION],
		).insert()
		cls.addClassCleanup(cls.doctype.delete)

	def test_docinfo_keys_and_values(self):
		with self.set_user(DESK_USER):
			doc = self.make_doc_with_history()
			frappe.response.docs = []
			getdoc(self.doctype.name, doc.name)
			docinfo = frappe.response.docinfo

		self.assertEqual(set(docinfo), DOCINFO_KEYS)
		for key, fields in DOCINFO_ROW_FIELDS.items():
			for row in docinfo[key]:
				self.assertEqual(set(row), fields, key)
		attachment = set(docinfo.attachments[0])
		self.assertLessEqual(ATTACHMENT_FIELDS, attachment)
		self.assertLessEqual(attachment - ATTACHMENT_FIELDS, ATTACHMENT_FIELDS_ADDED)
		self.assertEqual(set(docinfo.permissions), PERMISSION_KEYS)

		self.assertEqual([c.content for c in docinfo.comments], ["<p>Parity comment</p>\n"])
		self.assertEqual([s.user for s in docinfo.shared], [WORKSPACE_MANAGER])
		self.assertEqual([a.owner for a in docinfo.assignments], [WORKSPACE_MANAGER])
		self.assertEqual([a.file_name for a in docinfo.attachments], ["parity.txt"])
		self.assertEqual([c.content for c in docinfo.communications], ["Parity email"])
		self.assertEqual([m.value for m in docinfo.milestones], ["Closed"])
		self.assertEqual(len(docinfo.versions), 1)
		self.assertEqual(len(docinfo.views), 2)
		self.assertEqual(docinfo.tags, "parity")
		self.assertFalse(docinfo.is_document_followed)

	def make_doc_with_history(self):
		doc = frappe.get_doc(doctype=self.doctype.name, subject="Open").insert()
		doc.subject = "Closed"
		doc.save(ignore_version=False)
		doc.add_comment("Comment", "Parity comment")
		doc.add_tag("parity")
		doc.add_viewed(user=WORKSPACE_MANAGER)
		add_share(self.doctype.name, doc.name, WORKSPACE_MANAGER, read=1)
		add_assignment({"assign_to": [WORKSPACE_MANAGER], "doctype": doc.doctype, "name": doc.name})
		save_file("parity.txt", b"parity", doc.doctype, doc.name)
		frappe.get_doc(
			doctype="Communication",
			communication_type="Communication",
			content="Parity email",
			reference_doctype=doc.doctype,
			reference_name=doc.name,
		).insert(ignore_permissions=True)
		frappe.get_doc(
			doctype="Milestone",
			reference_type=doc.doctype,
			reference_name=doc.name,
			track_field="subject",
			value="Closed",
		).insert(ignore_permissions=True)
		return doc


class TestGetCountParity(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_user(DESK_USER, "Report Manager")
		with cls.set_user(DESK_USER):
			for _ in range(3):
				frappe.get_doc(doctype="ToDo", description="parity count").insert()

	def setUp(self):
		frappe.local.response_headers = frappe.local.response_headers.__class__()

	def count(self, **params):
		with self.set_user(DESK_USER):
			frappe.local.form_dict = frappe._dict(
				doctype="ToDo", filters=json.dumps([["description", "=", "parity count"]]), **params
			)
			return get_count()

	def test_count_that_hits_the_limit_is_cacheable(self):
		self.assertEqual(self.count(limit=3), 3)
		self.assertEqual(
			frappe.local.response_headers.get("Cache-Control"),
			"private,max-age=600,stale-while-revalidate=10800",
		)

	def test_count_under_the_limit_is_not_cacheable(self):
		self.assertEqual(self.count(limit=5), 3)
		self.assertIsNone(frappe.local.response_headers.get("Cache-Control"))

	def test_count_without_limit_is_exact_and_not_cacheable(self):
		self.assertEqual(self.count(), 3)
		self.assertIsNone(frappe.local.response_headers.get("Cache-Control"))

	def test_virtual_doctype_counts_itself(self):
		virtual = new_doctype(is_virtual=1, permissions=[DESK_PERMISSION]).insert()
		self.addCleanup(virtual.delete)
		calls = []

		class Controller(frappe.model.document.Document):
			@staticmethod
			def get_count(args):
				calls.append(dict(args))
				return 3

		with patch("frappe.controllers", new={frappe.local.site: {virtual.name: Controller}}):
			with self.set_user(DESK_USER):
				frappe.local.form_dict = frappe._dict(doctype=virtual.name, limit="3", distinct="true")
				self.assertEqual(get_count(), 3)

		self.assertIsNone(frappe.local.response_headers.get("Cache-Control"))
		self.assertEqual(len(calls), 1)
		self.assertLessEqual(
			{"doctype": virtual.name, "limit": "3", "distinct": "true"}.items(), calls[0].items()
		)


class TestSyncUserSettingsParity(IntegrationTestCase):
	def test_sync_writes_the_cached_row(self):
		make_user(DESK_USER, "Report Manager")
		self.addCleanup(frappe.cache.hdel, "_user_settings", f"ToDo::{DESK_USER}")

		with self.set_user(DESK_USER):
			for page_length in (20, 100):
				update_user_settings("ToDo", json.dumps({"page_length": page_length}), for_update=True)
				sync_user_settings()
				rows = frappe.db.sql(
					"select `user`, `doctype`, `data` from `__UserSettings` where `user`=%s", DESK_USER
				)
				self.assertEqual(
					[tuple(row) for row in rows],
					[(DESK_USER, "ToDo", json.dumps({"page_length": page_length}))],
				)


DOCINFO_KEYS = {
	"user_info",
	"comments",
	"shared",
	"assignment_logs",
	"attachment_logs",
	"info_logs",
	"like_logs",
	"workflow_logs",
	"doctype",
	"name",
	"attachments",
	"communications",
	"automated_messages",
	"versions",
	"assignments",
	"permissions",
	"views",
	"additional_timeline_content",
	"milestones",
	"is_document_followed",
	"tags",
	"document_email",
}
ATTACHMENT_FIELDS = {
	"name",
	"file_name",
	"file_url",
	"file_type",
	"file_size",
	"is_private",
	"attached_to_field",
	"folder",
}
ATTACHMENT_FIELDS_ADDED = {"creation", "owner"}
COMMENT_FIELDS = {"name", "creation", "content", "owner", "comment_type", "published"}
DOCINFO_ROW_FIELDS = {
	"comments": COMMENT_FIELDS,
	"assignment_logs": COMMENT_FIELDS,
	"attachment_logs": COMMENT_FIELDS,
	"shared": {
		"name",
		"creation",
		"modified",
		"modified_by",
		"owner",
		"docstatus",
		"idx",
		"user",
		"share_doctype",
		"share_name",
		"read",
		"write",
		"share",
		"submit",
		"everyone",
		"notify_by_email",
		"_user_tags",
		"_comments",
		"_assign",
		"_liked_by",
		"impersonate",
	},
	"assignments": {"name", "owner", "description", "status"},
	"versions": {"name", "owner", "creation", "data"},
	"views": {"name", "creation", "owner"},
	"milestones": {"name", "creation", "owner", "track_field", "value"},
	"communications": {
		"name",
		"communication_type",
		"communication_medium",
		"communication_date",
		"content",
		"sender",
		"sender_full_name",
		"cc",
		"bcc",
		"creation",
		"subject",
		"delivery_status",
		"_liked_by",
		"reference_doctype",
		"reference_name",
		"read_by_recipient",
		"recipients",
		"attachments",
	},
}
PERMISSION_KEYS = {
	"if_owner",
	"has_if_owner_enabled",
	"select",
	"read",
	"write",
	"create",
	"delete",
	"submit",
	"cancel",
	"amend",
	"print",
	"email",
	"report",
	"import",
	"export",
	"share",
}
LINK_MESSAGE = "Could not find Ref User: nobody@example.com, Row #1: Row User: ghost@example.com"
TRACEBACK_KEYS = {"exception", "exc"}


def make_user(email: str, *roles: str):
	if not frappe.db.exists("User", email):
		frappe.get_doc(doctype="User", email=email, first_name="Parity", send_welcome_email=0).insert(
			ignore_permissions=True
		)
	frappe.get_doc("User", email).add_roles(*roles)
