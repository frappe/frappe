import frappe
from frappe.boot import get_unseen_notes, get_user_pages_or_reports
from frappe.desk.doctype.note.note import _get_unseen_notes, mark_as_seen
from frappe.tests.utils import FrappeTestCase


class TestBootData(FrappeTestCase):
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

	def test_empty_allowed_reports_are_served_from_cache(self):
		from unittest.mock import patch

		frappe.set_user("Administrator")
		user = frappe.session.user
		frappe.cache.delete_value("has_role:Report", user=user)
		self.addCleanup(frappe.cache.delete_value, "has_role:Report", user=user)

		with patch("frappe.boot.has_permission", return_value=False) as has_perm:
			self.assertEqual(get_user_pages_or_reports("Report", cache=True), {})
			builds = has_perm.call_count
			self.assertGreaterEqual(builds, 1)

			frappe.local.cache.clear()

			self.assertEqual(get_user_pages_or_reports("Report", cache=True), {})
			self.assertEqual(has_perm.call_count, builds)

	def test_disabled_reports_are_not_allowed(self):
		frappe.set_user("Administrator")

		# role wiring decides which branch of the allowed-reports query a report comes from
		with_custom_role = self._make_report("Test Disabled Custom Role Report", disabled=1)
		frappe.get_doc(
			{
				"doctype": "Custom Role",
				"report": with_custom_role,
				"ref_doctype": "ToDo",
				"roles": [{"role": "System Manager"}],
			}
		).insert()

		without_roles = self._make_report("Test Disabled Roleless Report", disabled=1)
		frappe.db.delete("Has Role", {"parent": without_roles, "parenttype": "Report"})

		enabled = self._make_report("Test Enabled Report")

		allowed_reports = DeskViews.get_allowed_reports()
		self.assertNotIn(with_custom_role, allowed_reports)
		self.assertNotIn(without_roles, allowed_reports)
		self.assertIn(enabled, allowed_reports)

	def _make_report(self, report_name, disabled=0):
		return (
			frappe.get_doc(
				{
					"doctype": "Report",
					"ref_doctype": "ToDo",
					"report_name": report_name,
					"report_type": "Report Builder",
					"is_standard": "No",
					"disabled": disabled,
				}
			)
			.insert()
			.name
		)


class TestPermissionQueries(FrappeTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		cls.enable_safe_exec()
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
			dict(
				doctype="Server Script",
				name="test_report_permission_query",
				script_type="Permission Query",
				reference_doctype="Report",
				script="""conditions = f"(`tabReport`.is_standard = 'Yes' or `tabReport`.owner = '{frappe.session.user}')"
				""",
			)
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

		get_user_pages_or_reports("Report")
		allowed_reports = frappe.cache.get_value("has_role:Report", user=frappe.session.user)

		# Test user must not see admin user's report
		self.assertNotIn("Test Admin Report", allowed_reports)
		self.assertIn("Test User Report", allowed_reports)
