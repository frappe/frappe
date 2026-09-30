# Copyright (c) 2017, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.contacts.doctype.contact.contact import get_full_name
from frappe.email import get_contact_list, get_recipient_avatars
from frappe.permissions import add_permission, update_permission_property
from frappe.tests import IntegrationTestCase, timeout

EXTRA_TEST_RECORD_DEPENDENCIES = ["Contact", "Salutation"]


class TestContact(IntegrationTestCase):
	def test_check_default_email(self):
		emails = [
			{"email": "test1@example.com", "is_primary": 0},
			{"email": "test2@example.com", "is_primary": 0},
			{"email": "test3@example.com", "is_primary": 0},
			{"email": "test4@example.com", "is_primary": 1},
			{"email": "test5@example.com", "is_primary": 0},
		]
		contact = create_contact("Email", "Mr", emails=emails)

		self.assertEqual(contact.email_id, "test4@example.com")

	def test_check_default_phone_and_mobile(self):
		phones = [
			{"phone": "+91 0000000010", "is_primary_phone": 0, "is_primary_mobile_no": 0},
			{"phone": "+91 0000000011", "is_primary_phone": 0, "is_primary_mobile_no": 0},
			{"phone": "+91 0000000012", "is_primary_phone": 1, "is_primary_mobile_no": 0},
			{"phone": "+91 0000000013", "is_primary_phone": 0, "is_primary_mobile_no": 1},
		]
		contact = create_contact("Phone", "Mr", phones=phones)

		self.assertEqual(contact.phone, "+91 0000000012")
		self.assertEqual(contact.mobile_no, "+91 0000000013")

	def test_get_full_name(self):
		self.assertEqual(get_full_name(first="John"), "John")
		self.assertEqual(get_full_name(last="Doe"), "Doe")
		self.assertEqual(get_full_name(company="Doe Pvt Ltd"), "Doe Pvt Ltd")
		self.assertEqual(get_full_name(first="John", last="Doe"), "John Doe")
		self.assertEqual(get_full_name(first="John", middle="Jane"), "John Jane")
		self.assertEqual(get_full_name(first="John", last="Doe", company="Doe Pvt Ltd"), "John Doe")
		self.assertEqual(
			get_full_name(first="John", middle="Jane", last="Doe", company="Doe Pvt Ltd"),
			"John Jane Doe",
		)

	def test_get_contact_list(self):
		# First time from database
		results = get_contact_list("_Test Supplier")
		self.assertEqual(results[0].label, "test_contact@example.com")
		self.assertEqual(results[0].value, "test_contact@example.com")
		self.assertEqual(results[0].description, "_Test Contact For _Test Supplier")

		# Second time from cache
		results = get_contact_list("_Test Supplier")
		self.assertEqual(results[0].label, "test_contact@example.com")
		self.assertEqual(results[0].value, "test_contact@example.com")
		self.assertEqual(results[0].description, "_Test Contact For _Test Supplier")

	def test_get_recipient_avatars(self):
		suffix = frappe.generate_hash(length=8)
		with_photo = f"avatar-user-{suffix}@example.com"
		without_photo = f"avatar-nophoto-{suffix}@example.com"
		contact_only = f"avatar-contact-{suffix}@example.com"
		unknown = f"avatar-unknown-{suffix}@example.com"

		for email, image in ((with_photo, "/files/user.png"), (without_photo, None)):
			frappe.get_doc(
				doctype="User", email=email, first_name="Avatar", user_image=image, send_welcome_email=0
			).insert()

		for email, image in (
			(with_photo, "/files/contact-for-user.png"),
			(without_photo, "/files/contact-for-nophoto.png"),
			(contact_only, "/files/contact.png"),
		):
			contact = create_contact(
				"Avatar Contact", "Mr", emails=[{"email": email, "is_primary": 1}], save=False
			)
			contact.image = image
			contact.insert()

		def make_caller(can_read_contacts):
			role = frappe.new_doc("Role", role_name=frappe.generate_hash()).insert().name
			if can_read_contacts:
				add_permission("Contact", role, 0, ptype="read")
			return frappe.get_doc(
				doctype="User",
				email=f"caller-{frappe.generate_hash(length=8)}@example.com",
				first_name="Caller",
				send_welcome_email=0,
				roles=[{"role": role}],
			).insert()

		emails = frappe.as_json([with_photo.upper(), without_photo, contact_only, unknown])

		with self.set_user(make_caller(can_read_contacts=True).name):
			result = get_recipient_avatars(emails)

		# a user's own photo is never replaced by a contact's; contacts only fill the gaps
		self.assertEqual(result["user_info"][with_photo]["image"], "/files/user.png")
		self.assertEqual(
			result["contact_images"],
			{without_photo: "/files/contact-for-nophoto.png", contact_only: "/files/contact.png"},
		)
		self.assertNotIn(unknown, result["user_info"])

		# "All" grants owner-only read, which would still count as Contact access
		update_permission_property("Contact", "All", 0, "read", 0, validate=False)
		with self.set_user(make_caller(can_read_contacts=False).name):
			result = get_recipient_avatars(emails)

		self.assertEqual(result["user_info"][with_photo]["image"], "/files/user.png")
		self.assertEqual(result["contact_images"], {})

	def test_only_one_primary_contact_per_link(self):
		first_contact = create_contact("First Primary Contact", "Mr", save=False)
		first_contact.is_primary_contact = 1
		first_contact.append("links", {"link_doctype": "User", "link_name": "Administrator"})
		first_contact.insert()

		second_contact = create_contact("Second Primary Contact", "Mr", save=False)
		second_contact.is_primary_contact = 1
		second_contact.append("links", {"link_doctype": "User", "link_name": "Administrator"})
		second_contact.insert()

		self.assertFalse(first_contact.reload().is_primary_contact)
		self.assertTrue(second_contact.is_primary_contact)

	def test_promoting_contact_clears_existing_primary_contact(self):
		first_contact = create_contact("Existing Primary Contact", "Mr", save=False)
		first_contact.is_primary_contact = 1
		first_contact.append("links", {"link_doctype": "User", "link_name": "Administrator"})
		first_contact.insert()

		second_contact = create_contact("Promoted Primary Contact", "Mr", save=False)
		second_contact.append("links", {"link_doctype": "User", "link_name": "Administrator"})
		second_contact.insert()
		second_contact.is_primary_contact = 1
		second_contact.save()

		self.assertFalse(first_contact.reload().is_primary_contact)
		self.assertTrue(second_contact.is_primary_contact)

	@timeout(5, "Primary Contact validation did not lock the linked party")
	def test_primary_contact_locks_linked_party(self):
		contact = create_contact("Locking Primary Contact", "Mr", save=False)
		contact.is_primary_contact = 1
		contact.append("links", {"link_doctype": "User", "link_name": "Administrator"})

		with self.primary_connection():
			contact.insert()

			with self.secondary_connection():
				self.assertRaises(
					frappe.QueryTimeoutError,
					lambda: frappe.db.get_value("User", "Administrator", for_update=True, wait=False),
				)

	def test_primary_contact_fetches_existing_primaries_once(self):
		contact = create_contact("Multi-link Primary Contact", "Mr", save=False)
		contact.is_primary_contact = 1
		contact.append("links", {"link_doctype": "User", "link_name": "Administrator"})
		contact.append("links", {"link_doctype": "User", "link_name": "Guest"})

		with self.assertQueryCount(2):
			contact.validate_primary_contact()


def create_contact(name, salutation, emails=None, phones=None, save=True):
	doc = frappe.get_doc(
		{"doctype": "Contact", "first_name": name, "status": "Open", "salutation": salutation}
	)

	if emails:
		for d in emails:
			doc.add_email(d.get("email"), d.get("is_primary"))

	if phones:
		for d in phones:
			doc.add_phone(d.get("phone"), d.get("is_primary_phone"), d.get("is_primary_mobile_no"))

	if save:
		doc.insert()

	return doc
