# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.core.doctype.user.test_user import test_user
from frappe.tests import IntegrationTestCase
from frappe.www.third_party_apps import get_context


class TestThirdPartyApps(IntegrationTestCase):
	def test_app_is_limited_to_clients_with_a_token(self):
		own, other = (self.make_client(f"_Test Own Client {i}") for i in range(2))

		with test_user(roles=[]) as user, self.set_user(user.name):
			frappe.get_doc(
				doctype="OAuth Bearer Token",
				access_token=frappe.generate_hash(),
				client=own.name,
				expires_in=3600,
				scopes="all",
				status="Active",
				user=user.name,
			).insert(ignore_permissions=True)

			frappe.form_dict.app = other.name
			self.assertIsNone(self.get_app_context().get("app"))

			frappe.form_dict.app = own.name
			self.assertEqual(self.get_app_context().app["app_name"], own.app_name)

	def make_client(self, app_name):
		return frappe.get_doc(
			doctype="OAuth Client",
			app_name=app_name,
			scopes="all",
			redirect_uris="http://localhost",
			default_redirect_uri="http://localhost",
			grant_type="Authorization Code",
			response_type="Code",
		).insert(ignore_permissions=True)

	def get_app_context(self):
		context = frappe._dict()
		get_context(context)
		return context
