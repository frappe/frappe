from unittest.mock import MagicMock, patch

import requests

import frappe
from frappe.core.doctype.user_permission.test_user_permission import create_user
from frappe.integrations.frappe_providers.frappecloud_billing import (
	consulting_request,
	current_site_info,
)
from frappe.tests import IntegrationTestCase

# a site that really talks to Frappe Cloud: mock billing off, so these tests pass whether
# or not the developer running them has mock billing enabled in site_config
FC = {"fc_communication_secret": "secret", "developer_mode": 0, "mock_fc_billing": 0}
MOBILE_NO = "+91-9876543210"


def ok_response():
	response = MagicMock()
	response.status_code = 200
	return response


class TestFrappeCloudBilling(IntegrationTestCase):
	@patch.dict(frappe.conf, FC)
	@patch("requests.post", side_effect=requests.exceptions.SSLError)
	def test_current_site_info_ignores_network_errors(self, _):
		frappe.cache.delete_value(f"fc_current_site_info:{frappe.local.site}")
		self.assertIsNone(current_site_info())


class TestConsultingRequest(IntegrationTestCase):
	def setUp(self):
		self.enterContext(patch.dict(frappe.conf, FC))
		# a real System Manager, not Administrator, who bypasses every permission check
		manager = create_user("trial-banner-manager@example.com", "System Manager")
		self.enterContext(self.set_user(manager.name))

	@patch("requests.post", return_value=ok_response())
	def test_forwards_the_banner_payload_to_frappe_cloud(self, post):
		consulting_request(company="Acme Textiles", mobile_no=MOBILE_NO, note="Need GST help")

		url, kwargs = post.call_args[0][0], post.call_args[1]
		self.assertTrue(url.endswith("/api/method/press.saas.api.site.consulting_request"))
		self.assertEqual(
			kwargs["json"],
			{
				"company": "Acme Textiles",
				"mobile_no": MOBILE_NO,
				"note": "Need GST help",
				"current_business_tool": None,
				"no_of_employees": None,
			},
		)
		# the caller cannot choose who the request is attributed to
		self.assertEqual(kwargs["headers"]["X-Site-User"], frappe.utils.get_email_address())

	@patch("requests.post", return_value=ok_response())
	def test_the_optional_answers_amend_the_same_request(self, post):
		consulting_request(
			company="Acme Textiles",
			mobile_no=MOBILE_NO,
			current_business_tool="Tally",
			no_of_employees="11-50",
		)

		url, payload = post.call_args[0][0], post.call_args[1]["json"]
		self.assertTrue(url.endswith("/api/method/press.saas.api.site.consulting_request"))
		self.assertEqual(payload["current_business_tool"], "Tally")
		self.assertEqual(payload["no_of_employees"], "11-50")

	@patch("requests.post", return_value=ok_response())
	def test_rejects_a_phone_number_without_a_country_code(self, post):
		with self.assertRaises(frappe.InvalidPhoneNumberError):
			consulting_request(company="Acme Textiles", mobile_no="9876543210")

		post.assert_not_called()

	@patch("requests.post", return_value=ok_response())
	def test_rejects_a_blank_phone_number(self, post):
		with self.assertRaises(frappe.ValidationError):
			consulting_request(company="Acme Textiles", mobile_no="")

		post.assert_not_called()

	@patch("requests.post", return_value=ok_response())
	def test_rejects_a_blank_company(self, post):
		with self.assertRaises(frappe.ValidationError):
			consulting_request(company="   ", mobile_no=MOBILE_NO)

		post.assert_not_called()

	@patch("requests.post", return_value=ok_response())
	def test_rejects_a_user_without_the_system_manager_role(self, post):
		user = create_user("trial-banner-user@example.com", "Website Manager")
		self.enterContext(self.set_user(user.name))

		with self.assertRaises(frappe.PermissionError):
			consulting_request(company="Acme Textiles", mobile_no=MOBILE_NO)

		post.assert_not_called()

	@patch("requests.post", side_effect=requests.exceptions.SSLError)
	def test_reports_an_unreachable_frappe_cloud(self, _):
		with self.assertRaises(frappe.ValidationError):
			consulting_request(company="Acme Textiles", mobile_no=MOBILE_NO)

	@patch("requests.post")
	def test_reports_a_rejection_by_frappe_cloud(self, post):
		post.return_value.status_code = 500

		with self.assertRaises(frappe.ValidationError):
			consulting_request(company="Acme Textiles", mobile_no=MOBILE_NO)
