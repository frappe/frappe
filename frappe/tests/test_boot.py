import frappe
from frappe.desk.desk_views import DeskViews
from frappe.desk.doctype.module_sidebar.test_module_sidebar import developer_mode
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


class TestDeskViewModules(IntegrationTestCase):
	"""`module` on the Page, Report and Dashboard rows DeskViews ships.

	A DocType's module comes from its meta; nothing else has one client-side, which is why a Report,
	Page or Dashboard could never resolve to the sidebar it belongs to. The column rides along on
	queries that already run -- but `has_role` is assembled by THREE separate dict writes (custom
	role, standard role, no role), so a column added to the select alone reaches none of them. Each
	pass is asserted below through the report it is the only one to answer.
	"""

	def setUp(self):
		frappe.set_user("Administrator")

	def _report(self, name, roles=None):
		doc = frappe.get_doc(
			{
				"doctype": "Report",
				"report_name": name,
				"ref_doctype": "ToDo",
				"report_type": "Report Builder",
				"is_standard": "No",
				"module": "Desk",
				"roles": [{"role": role} for role in (roles or [])],
			}
		)
		doc.insert(ignore_if_duplicate=True)
		return doc

	def test_reports_carry_their_module_through_every_pass(self):
		no_role = self._report("Test Module Report No Role")
		standard_role = self._report("Test Module Report Standard Role", roles=["System Manager"])
		custom_role = self._report("Test Module Report Custom Role")
		frappe.get_doc(
			{
				"doctype": "Custom Role",
				"report": custom_role.name,
				"roles": [{"role": "System Manager"}],
			}
		).insert(ignore_if_duplicate=True)

		rows = DeskViews._build_user_pages_or_reports("Report", frappe.session.user)

		# each report is reachable by exactly one of the three passes: the custom-role one is
		# claimed by the first write, the role-bearing one is excluded from the no-role query, and
		# the bare one is only ever found there
		for report in (no_role, standard_role, custom_role):
			self.assertEqual(rows[report.name]["module"], "Desk", msg=report.name)

	def test_pages_carry_their_module(self):
		# `Page.validate` refuses *any* new page outside developer mode, `standard: No`
		# included, and the test site does not have it on. Nothing is written to disk: the
		# export is gated on `standard == "Yes"`.
		with developer_mode():
			page = frappe.get_doc(
				{
					"doctype": "Page",
					"page_name": "test-module-page",
					"title": "Test Module Page",
					"module": "Desk",
					"standard": "No",
				}
			)
			page.insert(ignore_if_duplicate=True)

		rows = DeskViews._build_user_pages_or_reports("Page", frappe.session.user)
		self.assertEqual(rows[page.name]["module"], "Desk")

	def test_dashboards_carry_their_module(self):
		from unittest.mock import patch

		chart = frappe.get_doc(
			{
				"doctype": "Dashboard Chart",
				"chart_name": "Test Module Chart",
				"chart_type": "Group By",
				"document_type": "ToDo",
				"group_by_based_on": "status",
				"filters_json": "[]",
				"is_standard": 0,
			}
		)
		chart.insert(ignore_if_duplicate=True)
		dashboard = frappe.get_doc(
			{
				"doctype": "Dashboard",
				"dashboard_name": "Test Module Dashboard",
				"module": "Desk",
				"charts": [{"chart": chart.name}],
			}
		)
		dashboard.insert(ignore_if_duplicate=True)

		# the permission gate is get_permitted_charts/cards, which this test is not about
		with patch("frappe.desk.doctype.dashboard.dashboard.get_permitted_charts", return_value=["chart"]):
			rows = DeskViews.get_allowed_dashboards()

		row = next(d for d in rows if d["name"] == dashboard.name)
		self.assertEqual(row["module"], "Desk")


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
