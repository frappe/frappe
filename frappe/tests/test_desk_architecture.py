# /desk-architecture: only in developer mode, and only for a System Manager.

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import set_request
from frappe.website.page_renderers.desk_architecture_page import DeskArchitecturePage
from frappe.website.path_resolver import PathResolver
from frappe.website.serve import get_response


class TestDeskArchitecturePage(IntegrationTestCase):
	def setUp(self):
		self.addCleanup(frappe.set_user, "Administrator")
		self.enterContext(patch.dict(frappe.conf, {"developer_mode": 1}))

	def tearDown(self):
		if hasattr(frappe.local, "request"):
			delattr(frappe.local, "request")

	def open_page(self, user):
		frappe.set_user(user)
		set_request(method="GET", path="/desk-architecture")
		return get_response()

	def test_the_route_does_not_exist_outside_developer_mode(self):
		with patch.dict(frappe.conf, {"developer_mode": 0}):
			renderer = PathResolver("desk-architecture").resolve()[1]
		self.assertNotIsInstance(renderer, DeskArchitecturePage)

	def test_a_guest_is_sent_to_login(self):
		response = self.open_page("Guest")
		self.assertIn(response.status_code, (301, 302))
		self.assertIn("/login?redirect-to=/desk-architecture", response.headers["Location"])

	def test_a_user_without_system_manager_is_refused(self):
		response = self.open_page(make_user("desk-architecture-reader@example.com").name)
		self.assertEqual(response.status_code, 403)

	def test_a_system_manager_sees_the_diagram(self):
		user = make_user("desk-architecture-admin@example.com")
		user.add_roles("System Manager")
		response = self.open_page(user.name)
		self.assertEqual(response.status_code, 200)
		page = response.get_data(as_text=True)
		self.assertIn('__("Desk v2 architecture")', page)
		self.assertIn('"id":"main"', page)

	def test_a_missing_node_shows_why_the_page_is_not_built(self):
		with patch("subprocess.run", side_effect=FileNotFoundError("node")):
			response = self.open_page("Administrator")
		self.assertIn("Diagram Not Built", response.get_data(as_text=True))

	def test_the_page_carries_the_translations_of_its_own_labels(self):
		translations = {
			"Layers": "Couches",
			'CI fails on this. Change the import so the lower layer does not use the higher one. If the rule is wrong, change {0} in the same PR and get a ruling: a new "may use" edge needs one.': "x",
			"Not a label of the page": "Pas une étiquette",
		}
		with (
			patch.object(frappe.local, "lang", "fr"),
			patch("frappe.translate.get_all_translations", return_value=translations),
		):
			page = self.open_page("Administrator").get_data(as_text=True)
		messages = json.loads(page.split("const MESSAGES = ", 1)[1].split(";\n", 1)[0])
		self.assertEqual(set(messages), set(translations) - {"Not a label of the page"})

	def test_a_site_s_own_english_wording_reaches_the_page(self):
		with (
			patch.object(frappe.local, "lang", "en"),
			patch("frappe.translate.get_all_translations", return_value={"Layers": "Levels"}),
		):
			page = self.open_page("Administrator").get_data(as_text=True)
		self.assertIn('const MESSAGES = {"Layers": "Levels"}', page)


def make_user(email):
	return frappe.get_doc(
		doctype="User", email=email, first_name="Architecture", user_type="System User"
	).insert(ignore_if_duplicate=True)
