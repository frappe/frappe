import frappe
from frappe.desk.desk_views import DeskViews
from frappe.desk.doctype.note.note import _get_unseen_notes, get_unseen_notes, mark_as_seen
from frappe.tests import IntegrationTestCase


class TestBootData(IntegrationTestCase):
	def test_get_unseen_notes(self):
		frappe.db.delete("Note")
		frappe.db.delete("Note Seen By")
		note = frappe.get_doc(
			{
				"doctype": "Note",
				"title": "Test Note",
				"notify_on_login": 1,
				"content": "Test Note 1",
				"public": 1,
			}
		)
		note.insert()

		frappe.set_user("test@example.com")
		_get_unseen_notes()
		unseen_notes = [d.title for d in get_unseen_notes()]
		self.assertListEqual(unseen_notes, ["Test Note"])

		mark_as_seen(note.name)
		unseen_notes = [d.title for d in get_unseen_notes()]
		self.assertListEqual(unseen_notes, [])

	def test_get_json_request_apps_includes_frappe(self):
		from frappe.boot import get_json_request_apps

		# frappe opts into native JSON request bodies via `use_json_request_body` in hooks.py
		apps = get_json_request_apps()
		self.assertIsInstance(apps, list)
		self.assertIn("frappe", apps)

	def test_setup_wizard_url_exposed_until_setup_complete(self):
		from unittest.mock import patch

		from frappe.boot import get_bootinfo

		frappe.set_user("Administrator")
		with (
			patch.object(frappe, "is_setup_complete", return_value=False),
			patch("frappe.boot.get_setup_wizard_url", return_value="/suite/setup") as resolve,
		):
			bootinfo = get_bootinfo()

		resolve.assert_called_once()
		self.assertEqual(bootinfo.setup_wizard_url, "/suite/setup")

	def test_notification_unread_count_is_not_served_from_cached_bootinfo(self):
		from unittest.mock import patch

		import frappe.sessions
		from frappe.desk.doctype.notification_log.notification_log import mark_as_read

		frappe.set_user("Administrator")
		user = frappe.session.user
		self.addCleanup(frappe.cache.hdel, "bootinfo", user)

		unread_before = frappe.db.count("Notification Log", {"read": 0, "for_user": user})
		notification = frappe.get_doc(
			doctype="Notification Log",
			for_user=user,
			from_user=user,
			subject="Quarterly payroll run needs approval",
		).insert(ignore_permissions=True)
		self.addCleanup(notification.delete, ignore_permissions=True)

		# a cached blob holding a stale count must not reach the client
		frappe.cache.hset(
			"bootinfo",
			user,
			frappe._dict({"user": {}, "notification_unread_count": 99}),
		)

		with patch.dict(frappe.conf, {"disable_session_cache": False}):
			bootinfo = frappe.sessions.get()
			self.assertEqual(bootinfo.from_cache, 1)
			self.assertEqual(bootinfo.notification_unread_count, unread_before + 1)

			mark_as_read(notification.name)
			bootinfo = frappe.sessions.get()
			self.assertEqual(bootinfo.from_cache, 1)
			self.assertEqual(bootinfo.notification_unread_count, unread_before)

	def test_empty_allowed_views_are_served_from_cache(self):
		from unittest.mock import patch

		# An empty allowed-set is a valid result and must be a cache hit; otherwise the
		# sidebar rebuilds it once per workspace on every desk/login load.
		frappe.set_user("Administrator")
		user = frappe.session.user
		frappe.cache.delete_value("has_role:Report", user=user)

		with patch.object(DeskViews, "_build_user_pages_or_reports", return_value={}) as build:
			self.assertEqual(DeskViews.get_allowed_reports(cache=True), {})
			self.assertEqual(build.call_count, 1)

			# fresh request: process-local cache cleared, redis cache stays warm
			frappe.local.cache.clear()

			self.assertEqual(DeskViews.get_allowed_reports(cache=True), {})
			self.assertEqual(build.call_count, 1)


class TestPermissionQueries(IntegrationTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		cls.enterClassContext(cls.enable_safe_exec())
		return super().setUpClass()

	def test_get_user_pages_or_reports_with_permission_query(self):
		# Create a ToDo custom report with admin user
		frappe.set_user("Administrator")
		frappe.get_doc(
			{
				"doctype": "Report",
				"ref_doctype": "ToDo",
				"report_name": "Test Admin Report",
				"report_type": "Report Builder",
				"is_standard": "No",
			}
		).insert()

		# Add permission query such that each user can only see their own custom reports
		frappe.get_doc(
			doctype="Server Script",
			name="test_report_permission_query",
			script_type="Permission Query",
			reference_doctype="Report",
			script="""conditions = f"(`tabReport`.is_standard = 'Yes' or `tabReport`.owner = '{frappe.session.user}')"
				""",
		).insert()

		# Create a ToDo custom report with test user
		frappe.set_user("test@example.com")
		frappe.get_doc(
			{
				"doctype": "Report",
				"ref_doctype": "ToDo",
				"report_name": "Test User Report",
				"report_type": "Report Builder",
				"is_standard": "No",
			}
		).insert(ignore_permissions=True)

		DeskViews.get_user_pages_or_reports("Report")
		allowed_reports = frappe.cache.get_value("has_role:Report", user=frappe.session.user)

		# Test user must not see admin user's report
		self.assertNotIn("Test Admin Report", allowed_reports)
		self.assertIn("Test User Report", allowed_reports)
