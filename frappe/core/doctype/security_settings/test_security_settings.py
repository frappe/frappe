# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

from datetime import UTC, datetime, timedelta

import frappe
from frappe.tests import IntegrationTestCase


class TestSecuritySettings(IntegrationTestCase):
	def test_public_policy_section_default(self):
		doc = frappe.get_doc(
			{
				"doctype": "Security Settings",
				"public_policy": None,
			}
		)
		section = doc.public_policy_section
		self.assertIn("Policy: https://frappe.io/security", section)

	def test_public_policy_section_custom(self):
		doc = frappe.get_doc(
			{
				"doctype": "Security Settings",
				"public_policy": "https://example.com/security-policy",
			}
		)
		section = doc.public_policy_section
		self.assertIn("Policy: https://example.com/security-policy", section)

	def test_public_languages_section_default(self):
		doc = frappe.get_doc({"doctype": "Security Settings"})
		section = doc.public_languages_section
		self.assertIn("Preferred-Languages: en", section)

	def test_public_languages_section_custom(self):
		doc = frappe.get_doc(
			{
				"doctype": "Security Settings",
				"public_languages": [
					{"language": "en"},
					{"language": "fr"},
				],
			}
		)
		section = doc.public_languages_section
		self.assertIn("Preferred-Languages: en, fr", section)

	def test_public_contacts_section_default(self):
		doc = frappe.get_doc({"doctype": "Security Settings"})
		section = doc.public_contacts_section
		self.assertIn("https://security.frappe.io", section)

	def test_public_contacts_section_email(self):
		doc = frappe.get_doc(
			{
				"doctype": "Security Settings",
				"public_contacts": [
					{"type": "Email", "contact": "security@example.com"},
				],
			}
		)
		section = doc.public_contacts_section
		self.assertIn("mailto:security@example.com", section)

	def test_public_contacts_section_phone(self):
		doc = frappe.get_doc(
			{
				"doctype": "Security Settings",
				"public_contacts": [
					{"type": "Phone", "contact": "+1234567890"},
				],
			}
		)
		section = doc.public_contacts_section
		self.assertIn("tel:+1234567890", section)

	def test_public_contacts_section_website(self):
		doc = frappe.get_doc(
			{
				"doctype": "Security Settings",
				"public_contacts": [
					{"type": "Website", "contact": "https://security.example.com"},
				],
			}
		)
		section = doc.public_contacts_section
		self.assertIn("https://security.example.com", section)

	def test_with_protocol_email_without_protocol(self):
		doc = frappe.get_doc({"doctype": "Security Settings"})
		result = doc.with_protocol("security@example.com", "Email")
		self.assertEqual(result, "mailto:security@example.com")

	def test_with_protocol_email_with_protocol(self):
		doc = frappe.get_doc({"doctype": "Security Settings"})
		result = doc.with_protocol("mailto:security@example.com", "Email")
		self.assertEqual(result, "mailto:security@example.com")

	def test_with_protocol_phone_without_protocol(self):
		doc = frappe.get_doc({"doctype": "Security Settings"})
		result = doc.with_protocol("+1234567890", "Phone")
		self.assertEqual(result, "tel:+1234567890")

	def test_with_protocol_phone_with_protocol(self):
		doc = frappe.get_doc({"doctype": "Security Settings"})
		result = doc.with_protocol("tel:+1234567890", "Phone")
		self.assertEqual(result, "tel:+1234567890")

	def test_with_protocol_website(self):
		doc = frappe.get_doc({"doctype": "Security Settings"})
		result = doc.with_protocol("https://example.com", "Website")
		self.assertEqual(result, "https://example.com")

	def test_security_txt_full(self):
		doc = frappe.get_doc(
			{
				"doctype": "Security Settings",
				"public_policy": "https://example.com/policy",
				"public_contacts": [
					{"type": "Email", "contact": "security@example.com"},
				],
				"public_languages": [
					{"language": "en"},
				],
				"public_expires": datetime.now() + timedelta(days=365),
			}
		)
		security_txt = doc.security_txt
		self.assertIn("Policy: https://example.com/policy", security_txt)
		self.assertIn("mailto:security@example.com", security_txt)
		self.assertIn("Preferred-Languages: en", security_txt)
		self.assertIn("Expires:", security_txt)

	def test_validate_public_policy_with_http(self):
		doc = frappe.get_doc(
			{
				"doctype": "Security Settings",
				"public_policy": "http://example.com",
			}
		)
		self.assertRaises(frappe.ValidationError, doc.validate_public_policy)

	def test_validate_public_policy_with_https(self):
		doc = frappe.get_doc(
			{
				"doctype": "Security Settings",
				"public_policy": "https://example.com",
			}
		)
		# Should not raise
		doc.validate_public_policy()

	def test_validate_public_contacts_invalid_email(self):
		doc = frappe.get_doc(
			{
				"doctype": "Security Settings",
				"public_contacts": [
					{"type": "Email", "contact": "invalid-email"},
				],
			}
		)
		self.assertRaises(frappe.ValidationError, doc.validate_public_contacts)

	def test_validate_public_contacts_valid_email(self):
		doc = frappe.get_doc(
			{
				"doctype": "Security Settings",
				"public_contacts": [
					{"type": "Email", "contact": "security@example.com"},
				],
			}
		)
		# Should not raise
		doc.validate_public_contacts()

	def test_validate_public_contacts_invalid_phone(self):
		doc = frappe.get_doc(
			{
				"doctype": "Security Settings",
				"public_contacts": [
					{"type": "Phone", "contact": "not-a-phone"},
				],
			}
		)
		self.assertRaises(frappe.ValidationError, doc.validate_public_contacts)

	def test_validate_public_contacts_valid_phone(self):
		doc = frappe.get_doc(
			{
				"doctype": "Security Settings",
				"public_contacts": [
					{"type": "Phone", "contact": "+1234567890"},
				],
			}
		)
		# Should not raise
		doc.validate_public_contacts()

	def test_validate_public_contacts_website_without_https(self):
		doc = frappe.get_doc(
			{
				"doctype": "Security Settings",
				"public_contacts": [
					{"type": "Website", "contact": "http://example.com"},
				],
			}
		)
		self.assertRaises(frappe.ValidationError, doc.validate_public_contacts)

	def test_validate_public_contacts_valid_website(self):
		doc = frappe.get_doc(
			{
				"doctype": "Security Settings",
				"public_contacts": [
					{"type": "Website", "contact": "https://example.com"},
				],
			}
		)
		# Should not raise
		doc.validate_public_contacts()

	def test_validate_expires_past(self):
		doc = frappe.get_doc(
			{
				"doctype": "Security Settings",
				"public_expires": datetime.now() - timedelta(days=1),
			}
		)
		self.assertRaises(frappe.ValidationError, doc.validate_expires)

	def test_validate_expires_future(self):
		doc = frappe.get_doc(
			{
				"doctype": "Security Settings",
				"public_expires": datetime.now() + timedelta(days=365),
			}
		)
		# Should not raise
		doc.validate_expires()

	@IntegrationTestCase.change_settings("System Settings", {"time_zone": "Etc/UTC"})
	def test_public_expires_section_future_date(self):
		from datetime import timezone

		future_date = datetime(2027, 12, 31, 23, 59, 59)
		doc = frappe.get_doc(
			{
				"doctype": "Security Settings",
				"public_expires": future_date,
			}
		)
		section = doc.public_expires_section
		self.assertIn("2027-12-31T23:59:59Z", section)

	@IntegrationTestCase.change_settings("System Settings", {"time_zone": "Asia/Kolkata"})
	def test_public_expires_section_string(self):
		doc = frappe.get_doc(
			{
				"doctype": "Security Settings",
				"public_expires": "2028-01-01T05:29:59",
			}
		)
		section = doc.public_expires_section
		self.assertIn("2027-12-31T23:59:59Z", section)

	def test_public_expires_section_default(self):
		doc = frappe.get_doc({"doctype": "Security Settings"})
		section = doc.public_expires_section
		# Default is 1 year from now
		self.assertIn("Expires:", section)
		self.assertIn("T", section)  # ISO format
