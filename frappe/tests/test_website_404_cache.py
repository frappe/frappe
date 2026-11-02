from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import set_request
from frappe.website.serve import get_response
from frappe.website.utils import clear_website_cache


def website_permission_for_test(doc, ptype, user, verbose=False):
	return user == "website-cache-user@example.com"


class TestWebsite404Cache(IntegrationTestCase):
	def test_permission_denial_does_not_cache_404_for_other_users(self):
		frappe.set_user("Administrator")
		frappe.get_doc(
			doctype="User",
			email="website-cache-user@example.com",
			first_name="Website Cache User",
			user_type="Website User",
			send_welcome_email=0,
		).insert(ignore_if_duplicate=True)
		page = frappe.get_doc(
			doctype="Web Page",
			title="Website Cache Test",
			route="website-cache-test",
			published=1,
			content_type="HTML",
			main_section_html="Website cache test",
		).insert()
		meta = frappe.get_meta("Web Page")
		original_get_hooks = frappe.get_hooks

		def get_test_hooks(hook=None, *args, **kwargs):
			if hook == "has_website_permission":
				return {"Web Page": ["frappe.tests.test_website_404_cache.website_permission_for_test"]}
			return original_get_hooks(hook, *args, **kwargs)

		previous_force_cache = frappe.flags.get("force_website_cache")
		try:
			clear_website_cache()
			with (
				patch.object(meta, "allow_guest_to_view", 0),
				patch.object(frappe, "get_hooks", get_test_hooks),
			):
				frappe.flags.force_website_cache = True
				frappe.set_user("Guest")
				set_request(method="GET", path=f"/{page.route}")
				self.assertEqual(get_response().status_code, 404)

				frappe.set_user("website-cache-user@example.com")
				set_request(method="GET", path=f"/{page.route}")
				response = get_response()
				self.assertEqual(response.status_code, 200)
				self.assertIn(b"Website cache test", response.get_data())
		finally:
			frappe.flags.force_website_cache = previous_force_cache
			frappe.set_user("Administrator")
			clear_website_cache()
