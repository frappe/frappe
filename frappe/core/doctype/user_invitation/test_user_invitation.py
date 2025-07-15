# Copyright (c) 2025, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.core.api.user_invitation import accept_invitation, invite_by_email
from frappe.core.doctype.user_invitation.user_invitation import mark_expired_invitations
from frappe.tests import IntegrationTestCase

emails = [
	"test_user_invite1@example.com",
	"test_user_invite2@example.com",
	"test_user_invite3@example.com",
]


class IntegrationTestUserInvitation(IntegrationTestCase):
	"""
	Integration tests for UserInvitation.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")

	@classmethod
	def tearDownClass(cls):
		super().tearDownClass()
		frappe.db.delete("User Invitation")
		frappe.db.delete("Email Queue")
		for user_email in emails:
			if frappe.db.exists("User", user_email):
				frappe.delete_doc("User", user_email)
		# some of the code under test commit internally
		frappe.db.commit()  # nosemgrep

	def setUp(self):
		super().setUp()
		frappe.db.delete("User Invitation")
		frappe.db.delete("Email Queue")

	def test_insert_invitation(self):
		invitation = self.get_dummy_invitation()
		self.assertEqual(len(self.get_sent_email_names()), 0)
		invitation.insert()
		self.assertEqual(invitation.invited_by, "Administrator")
		self.assertEqual(invitation.status, "Pending")
		self.assertEqual(type(invitation.email_sent_at), str)
		self.assertEqual(type(invitation.key), str)
		sent_emails = self.get_sent_emails_messages()
		self.assertEqual(len(sent_emails), 1)
		self.assertIn("invited", sent_emails[0].message.lower())

	def test_update_invitation_status_to_expired(self):
		invitation = self.get_dummy_invitation()
		invitation.insert()
		self.assertEqual(len(self.get_sent_email_names()), 1)
		invitation.status = "Expired"
		invitation.save()
		sent_emails = self.get_sent_emails_messages()
		self.assertEqual(len(sent_emails), 2)
		self.assertIn("expired", sent_emails[0].message.lower())

	def test_delete_pending_invitation(self):
		invitation = self.get_dummy_invitation()
		invitation.insert()
		self.assertEqual(len(self.get_sent_email_names()), 1)
		self.assertEqual(invitation.status, "Pending")
		frappe.delete_doc("User Invitation", invitation.name)
		sent_emails = self.get_sent_emails_messages()
		self.assertEqual(len(sent_emails), 2)
		self.assertIn("revoked", sent_emails[0].message.lower())

	def test_delete_accepted_invitation(self):
		invitation = self.get_dummy_invitation()
		invitation.insert()
		self.assertEqual(len(self.get_sent_email_names()), 1)
		invitation.status = "Accepted"
		invitation.save()
		frappe.delete_doc("User Invitation", invitation.name)
		self.assertEqual(len(self.get_sent_email_names()), 1)

	def test_delete_expired_invitation(self):
		invitation = self.get_dummy_invitation()
		invitation.insert()
		self.assertEqual(len(self.get_sent_email_names()), 1)
		invitation.status = "Expired"
		invitation.save()
		self.assertEqual(len(self.get_sent_email_names()), 2)
		frappe.delete_doc("User Invitation", invitation.name)
		self.assertEqual(len(self.get_sent_email_names()), 2)

	def test_mark_expired_invitations(self):
		invitation = self.get_dummy_invitation()
		invitation.insert()
		# the status of invitations older than 3 days should be set to expired
		invitation.db_set("creation", frappe.utils.add_days(frappe.utils.now(), -4))
		mark_expired_invitations()
		invitation.reload()
		self.assertEqual(invitation.status, "Expired")

	def test_invite_by_email_api(self):
		user_email = emails[0]
		user = frappe.get_doc(
			doctype="User",
			user_type="Website User",
			email=user_email,
			first_name="Test1",
			send_welcome_email=False,
		).insert()
		invited_email = emails[1]
		frappe.get_doc(
			doctype="User Invitation",
			email=invited_email,
			role="System Manager",
			redirect_to_path="/abc",
			app_name="frappe",
		).insert()
		self.assertEqual(len(self.get_sent_email_names()), 1)
		email_to_invite = emails[2]
		res = invite_by_email(
			emails=", ".join([user_email, invited_email, email_to_invite]),
			role="System Manager",
			redirect_to_path="/xyz",
		)
		self.assertSequenceEqual(res["existing_user_emails"], [user_email])
		self.assertSequenceEqual(res["existing_invited_emails"], [invited_email])
		self.assertSequenceEqual(res["invited_emails"], [email_to_invite])
		self.assertEqual(len(self.get_sent_email_names()), 2)
		frappe.delete_doc("User", user.name)

	def test_accept_invitation_api_pass_redirect(self):
		invitation = frappe.get_doc(
			doctype="User Invitation",
			email=emails[0],
			role="System Manager",
			redirect_to_path="/abc",
			app_name="frappe",
		).insert()
		self.assertEqual(len(frappe.get_all("User", filters={"email": invitation.email}, pluck="name")), 0)
		accept_invitation(invitation.key)
		res = frappe.local.response
		self.assertEqual(res.type, "redirect")
		self.assertRegex(res.location, r"^/update-password\?key=.+&redirect_to=/abc$")
		user = frappe.get_doc("User", invitation.email)
		frappe.delete_doc("User Invitation", invitation.name)
		frappe.delete_doc("User", user.name)

	def test_accept_invitation_api_direct_redirect(self):
		invitation = frappe.get_doc(
			doctype="User Invitation",
			email=emails[0],
			role="System Manager",
			redirect_to_path="/abc",
			app_name="frappe",
		).insert()
		self.assertEqual(len(frappe.get_all("User", filters={"email": invitation.email}, pluck="name")), 0)
		original_disable_user_pass_login = frappe.get_system_settings("disable_user_pass_login")
		frappe.db.set_single_value("System Settings", "disable_user_pass_login", 1)
		accept_invitation(invitation.key)
		frappe.db.set_single_value(
			"System Settings", "disable_user_pass_login", original_disable_user_pass_login
		)
		res = frappe.local.response
		self.assertEqual(res.type, "redirect")
		self.assertRegex(res.location, r"^/abc$")
		user = frappe.get_doc("User", invitation.email)
		frappe.delete_doc("User Invitation", invitation.name)
		frappe.delete_doc("User", user.name)

	def get_dummy_invitation(self):
		return frappe.get_doc(
			doctype="User Invitation",
			email=emails[0],
			role="System Manager",
			redirect_to_path="/abc",
			app_name="frappe",
		)

	def get_sent_email_names(self):
		return frappe.db.get_all("Email Queue", filters={"status": "Sent"}, fields=["name"])

	def get_sent_emails_messages(self):
		return frappe.db.get_all("Email Queue", filters={"status": "Sent"}, fields=["message"])
