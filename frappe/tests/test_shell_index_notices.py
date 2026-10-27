# The index boot's notices: the site's setup nudge and what's new, for the managers who act on them.

import json
from unittest.mock import patch

import frappe
from frappe.desk.page.setup_wizard.setup_wizard import get_setup_wizard_url
from frappe.shell import SHELL_ROOT
from frappe.shell.boot import get_boot
from frappe.shell.index_notices import index_notices, read_whats_new
from frappe.tests import IntegrationTestCase
from frappe.utils.change_log import get_versions

ROLE = "Shell Notices Probe"
USER = "shell-notices-probe@example.com"
SYSTEM_MANAGER = "shell-notices-system-manager@example.com"
WORKSPACE_MANAGER = "shell-notices-workspace-manager@example.com"

# Frappe ships change log files from v5 on, so a person who last saw v7 has notes to read.
OLD_FRAPPE = "7.0.0"


class TestIndexNotices(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.db.savepoint("index_notices_test")
		self.addCleanup(lambda: frappe.db.rollback(save_point="index_notices_test"))
		self.probe_user(USER, ROLE)
		self.probe_user(SYSTEM_MANAGER, "System Manager")
		self.probe_user(WORKSPACE_MANAGER, "Workspace Manager")
		self.addCleanup(frappe.clear_document_cache, "Installed Applications", "Installed Applications")
		self.addCleanup(frappe.clear_document_cache, "System Settings", "System Settings")
		self.addCleanup(setattr, frappe.local, "system_settings", None)

	def probe_user(self, email: str, role: str):
		if not frappe.db.exists("Role", role):
			frappe.get_doc(doctype="Role", role_name=role, desk_access=1).insert()
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				doctype="User",
				email=email,
				first_name="Notices Probe",
				user_type="System User",
				send_welcome_email=0,
				roles=[{"role": role}],
			).insert()
		self.saw_old_frappe(email)

	def saw_old_frappe(self, email: str):
		versions = get_versions()
		versions["frappe"]["version"] = OLD_FRAPPE
		frappe.db.set_value("User", email, "last_known_versions", json.dumps(versions))

	def leave_setup_unfinished(self):
		frappe.set_user("Administrator")
		installed = frappe.get_doc("Installed Applications")
		for row in installed.installed_applications:
			if row.app_name == "frappe":
				row.is_setup_complete = 0
		installed.save()
		# `is_setup_complete` is request-cached, and a test is one long request.
		frappe.local.request_cache.clear()

	def notices(self, user: str) -> dict:
		frappe.set_user(user)
		return get_boot(f"/{SHELL_ROOT}")["notices"]

	def test_a_person_without_a_manager_role_gets_none_and_pays_no_query(self):
		self.leave_setup_unfinished()
		self.assertEqual(self.notices(USER), {})

		with self.assertQueryCount(0):
			self.assertEqual(index_notices(setup_complete=True), {})
			self.assertEqual(index_notices(setup_complete=False), {})

	def test_a_system_manager_on_a_finished_site_gets_whats_new_and_no_setup_nudge(self):
		notices = self.notices(SYSTEM_MANAGER)

		self.assertNotIn("setup", notices)
		self.assertIn({"title": "Frappe Framework", "version": frappe.__version__}, notices["whats_new"])

	def test_an_unfinished_site_gets_one_setup_nudge_to_the_wizard_and_no_whats_new(self):
		self.leave_setup_unfinished()

		notices = self.notices(SYSTEM_MANAGER)

		self.assertEqual(notices, {"setup": {"apps": ["Frappe Framework"], "route": get_setup_wizard_url()}})

	def test_a_workspace_manager_gets_whats_new_but_never_the_setup_nudge(self):
		self.assertIn("whats_new", self.notices(WORKSPACE_MANAGER))

		self.leave_setup_unfinished()
		self.assertEqual(self.notices(WORKSPACE_MANAGER), {})

	def test_reading_whats_new_gives_the_notes_as_html_and_records_them_seen(self):
		frappe.set_user(SYSTEM_MANAGER)

		entries = read_whats_new()

		frappe_entry = next(entry for entry in entries if entry["title"] == "Frappe Framework")
		self.assertEqual(frappe_entry["version"], frappe.__version__)
		self.assertTrue(frappe_entry["notes"])
		self.assertTrue(all(note["html"].strip().startswith("<") for note in frappe_entry["notes"]))
		self.assertNotIn("whats_new", self.notices(SYSTEM_MANAGER))

	def test_only_a_manager_may_read_whats_new(self):
		frappe.set_user(USER)

		self.assertRaises(frappe.PermissionError, read_whats_new)

	def test_a_manager_who_has_seen_every_version_pays_no_git_call(self):
		frappe.set_user(SYSTEM_MANAGER)
		read_whats_new()

		with patch("frappe.shell.index_notices.get_change_log") as change_log:
			self.assertNotIn("whats_new", self.notices(SYSTEM_MANAGER))
		change_log.assert_not_called()

	def test_the_system_setting_turns_whats_new_off(self):
		frappe.db.set_single_value("System Settings", "disable_change_log_notification", 1)
		frappe.clear_document_cache("System Settings", "System Settings")
		frappe.local.system_settings = None

		self.assertNotIn("whats_new", self.notices(SYSTEM_MANAGER))
