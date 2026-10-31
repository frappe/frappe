# Copyright (c) 2025, Frappe Technologies and Contributors
# See license.txt

import re
from unittest.mock import MagicMock, patch

import frappe
import frappe.utils
from frappe.core.api.user_invitation import (
	_accept_invitation,
	cancel_invitation,
	get_pending_invitations,
	invite_by_email,
)
from frappe.core.doctype.user_invitation.user_invitation import mark_expired_invitations
from frappe.tests import IntegrationTestCase

emails = [
	"test_user_invite1@example.com",
	"test_user_invite2@example.com",
	"test_user_invite3@example.com",
	"test_user_invite4@example.com",
	"test_user_invite5@example.com",
	"test_user_invite6@example.com",
]


class IntegrationTestUserInvitation(IntegrationTestCase):
	"""
	Integration tests for UserInvitation.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		user = frappe.new_doc("User")
		user.first_name = "Test"
		user.last_name = "123"
		user.email = emails[0]
		user.append_roles("System Manager")
		user.insert()
		frappe.set_user(emails[0])

	@classmethod
	def tearDownClass(cls):
		super().tearDownClass()
		IntegrationTestUserInvitation.delete_all_invitations()
		IntegrationTestUserInvitation.delete_all_user_roles()
		frappe.db.delete("Email Queue")
		for user_email in emails:
			if frappe.db.exists("User", user_email):
				frappe.delete_doc("User", user_email)
		frappe.set_user("Administrator")
		# some of the code under test commit internally
		frappe.db.commit()  # nosemgrep

	@classmethod
	def delete_all_user_roles(cls):
		query = "DELETE FROM `tabUser Role`"
		frappe.db.sql(cls.normalize_sql(query))

	@classmethod
	def delete_all_invitations(cls):
		query = "DELETE FROM `tabUser Invitation`"
		frappe.db.sql(cls.normalize_sql(query))

	@classmethod
	def delete_invitation(cls, name: str):
		query = "DELETE FROM `tabUser Invitation` WHERE name = %s"
		frappe.db.sql(cls.normalize_sql(query), name)

	def setUp(self):
		super().setUp()
		IntegrationTestUserInvitation.delete_all_invitations()
		IntegrationTestUserInvitation.delete_all_user_roles()
		frappe.db.delete("Email Queue")

	def test_insert_invitation(self):
		invitation = self.get_dummy_invitation()
		self.assertEqual(len(self.get_email_names()), 0)
		invitation.insert()
		frappe.db.commit()
		self.assertEqual(invitation.invited_by, frappe.session.user)
		self.assertEqual(invitation.status, "Pending")
		self.assertIsInstance(invitation.email_sent_at, str)
		self.assertIsInstance(invitation.key, str)
		self.assertIsInstance(invitation.roles, list)
		sent_emails = self.get_email_messages()
		self.assertEqual(len(sent_emails), 1)
		self.assertIn("invited", sent_emails[0].message.lower())

	def test_update_invitation_status_to_expired(self):
		invitation = self.get_dummy_invitation()
		invitation.insert()
		frappe.db.commit()
		self.assertEqual(len(self.get_email_names()), 1)
		invitation.expire()
		frappe.db.commit()
		emails = self.get_email_messages(False)
		self.assertEqual(len(emails), 2)
		self.assertIn("expired", emails[0].message.lower())

	def test_cancel_pending_invitation(self):
		invitation = self.get_dummy_invitation()
		invitation.insert()
		self.assertEqual(len(self.get_email_names(False)), 1)
		self.assertEqual(invitation.status, "Pending")
		invitation.cancel_invite()
		sent_emails = self.get_email_messages(False)
		self.assertEqual(len(sent_emails), 2)
		self.assertIn("cancelled", sent_emails[0].message.lower())

	def test_cancel_accepted_invitation(self):
		invitation = self.get_dummy_invitation()
		invitation.insert()
		self.assertEqual(len(self.get_email_names(False)), 1)
		invitation.status = "Accepted"
		invitation.save()
		invitation.cancel_invite()
		self.assertEqual(len(self.get_email_names(False)), 1)

	def test_cancel_expired_invitation(self):
		invitation = self.get_dummy_invitation()
		invitation.insert()
		self.assertEqual(len(self.get_email_names(False)), 1)
		invitation.expire()
		self.assertEqual(len(self.get_email_names(False)), 2)
		invitation.cancel_invite()
		self.assertEqual(len(self.get_email_names(False)), 2)

	def test_mark_expired_invitations(self):
		invitation = self.get_dummy_invitation()
		invitation.insert()
		# the status of invitations older than 3 days should be set to expired
		invitation.db_set("creation", frappe.utils.add_days(frappe.utils.now(), -4))
		mark_expired_invitations()
		invitation.reload()
		self.assertEqual(invitation.status, "Expired")

	def test_invite_by_email_api(self):
		accepted_invite_email = emails[1]
		invitation = frappe.get_doc(
			doctype="User Invitation",
			email=accepted_invite_email,
			roles=[dict(role="System Manager")],
			redirect_to_path="/abc",
			app_name="frappe",
		).insert()
		invitation.accept()
		self.assertEqual(len(self.get_email_names(False)), 1)
		pending_invite_email = emails[2]
		frappe.get_doc(
			doctype="User Invitation",
			email=pending_invite_email,
			roles=[dict(role="System Manager")],
			redirect_to_path="/abc",
			app_name="frappe",
		).insert()
		self.assertEqual(len(self.get_email_names(False)), 2)
		email_to_invite = emails[3]
		res = invite_by_email(
			emails=", ".join([accepted_invite_email, pending_invite_email, email_to_invite]),
			roles=["System Manager"],
			redirect_to_path="/xyz",
		)
		self.assertSequenceEqual(res["disabled_user_emails"], [])
		self.assertSequenceEqual(res["accepted_invite_emails"], [accepted_invite_email])
		self.assertSequenceEqual(res["pending_invite_emails"], [pending_invite_email])
		self.assertSequenceEqual(res["invited_emails"], [email_to_invite])
		self.assertEqual(len(self.get_email_names(False)), 3)
		user = frappe.get_doc("User", invitation.email)
		IntegrationTestUserInvitation.delete_invitation(invitation.name)
		frappe.delete_doc("User", user.name)

	def test_invite_by_email_api_disabled_user(self):
		user = frappe.new_doc("User")
		user.first_name = "Random"
		user.last_name = "User"
		user.email = emails[5]
		user.append_roles("System Manager")
		user.insert()
		user.reload()
		user.enabled = 0
		user.save()
		res = invite_by_email(
			emails=user.email,
			roles=["System Manager"],
			redirect_to_path="/xyz",
		)
		self.assertSequenceEqual(res["disabled_user_emails"], [user.email])
		self.assertSequenceEqual(res["accepted_invite_emails"], [])
		self.assertSequenceEqual(res["pending_invite_emails"], [])
		self.assertSequenceEqual(res["invited_emails"], [])
		frappe.delete_doc("User", user.email)

	def test_accept_invitation_api_pass_redirect(self):
		invitation = frappe.get_doc(
			doctype="User Invitation",
			email=emails[1],
			roles=[dict(role="System Manager")],
			redirect_to_path="/abc",
			app_name="frappe",
		).insert()
		self.assertEqual(len(frappe.get_all("User", filters={"email": invitation.email}, pluck="name")), 0)
		self.assertEqual(len(self.get_email_names(False)), 1)
		key = invitation.send_invitation_mail()
		self.assertEqual(len(self.get_email_names(False)), 2)
		# accepting commits
		with (
			self.change_settings("System Settings", {"disable_user_pass_login": 0}, commit=True),
			self.set_user("Guest"),
		):
			_accept_invitation(key, True)
		res = frappe.local.response
		self.assertEqual(res.type, "redirect")
		pattern = f"^{re.escape(frappe.utils.get_url(''))}/update-password\\?key=.+&redirect_to=/abc$"
		self.assertRegex(res.location, pattern)
		user = frappe.get_doc("User", invitation.email)
		IntegrationTestUserInvitation.delete_invitation(invitation.name)
		frappe.delete_doc("User", user.name)

	def test_accept_invitation_api_direct_redirect(self):
		invitation = frappe.get_doc(
			doctype="User Invitation",
			email=emails[1],
			roles=[dict(role="System Manager")],
			redirect_to_path="/abc",
			app_name="frappe",
		).insert()
		self.assertEqual(len(frappe.get_all("User", filters={"email": invitation.email}, pluck="name")), 0)
		self.assertEqual(len(self.get_email_names(False)), 1)
		key = invitation.send_invitation_mail()
		self.assertEqual(len(self.get_email_names(False)), 2)
		# accepting commits
		with (
			self.change_settings("System Settings", {"disable_user_pass_login": 1}, commit=True),
			self.set_user("Guest"),
		):
			_accept_invitation(key, True)
		res = frappe.local.response
		self.assertEqual(res.type, "redirect")
		pattern = f"^{re.escape(frappe.utils.get_url(''))}/abc$"
		self.assertRegex(res.location, pattern)
		user = frappe.get_doc("User", invitation.email)
		IntegrationTestUserInvitation.delete_invitation(invitation.name)
		frappe.delete_doc("User", user.name)

	def test_accept_invitation_api_refuses_another_logged_in_user(self):
		invitation = self.get_dummy_invitation().insert()
		key = invitation.send_invitation_mail()
		self.assertRaisesRegex(frappe.ValidationError, "You are logged in as", _accept_invitation, key, True)
		invitation.reload()
		self.assertEqual(invitation.status, "Pending")
		self.assertEqual(invitation.key, frappe.utils.sha256_hash(key))
		self.assertFalse(invitation.user)

	def test_accept_invitation_api_mixed_case_invitee(self):
		user = frappe.new_doc("User", first_name="Invited", email=emails[4], send_welcome_email=0).insert()
		self.addCleanup(frappe.delete_doc, "User", user.name)
		invitation = self.get_dummy_invitation()
		invitation.email = emails[4].upper()
		invitation.insert()
		key = invitation.send_invitation_mail()
		with self.set_user(user.name):
			_accept_invitation(key, True)
		self.assertEqual(frappe.local.response.type, "redirect")
		self.assertEqual(frappe.db.get_value("User Invitation", invitation.name, "status"), "Accepted")

	def test_accept_invitation_api_checks_status_before_session(self):
		invitation = self.get_dummy_invitation().insert()
		key = invitation.send_invitation_mail()
		invitation.cancel_invite()
		self.assertRaisesRegex(
			frappe.ValidationError, "Invitation is cancelled", _accept_invitation, key, True
		)

	def test_accept_invitation_api_logged_in_invitee(self):
		user = frappe.new_doc("User")
		user.first_name = "Invited"
		user.email = emails[4]
		user.send_welcome_email = 0
		user.insert()
		self.addCleanup(frappe.delete_doc, "User", user.name)
		invitation = frappe.get_doc(
			doctype="User Invitation",
			email=user.email,
			roles=[dict(role="System Manager")],
			redirect_to_path="/abc",
			app_name="frappe",
		).insert()
		key = invitation.send_invitation_mail()
		login_manager = MagicMock()
		with (
			self.set_user(user.name),
			patch.object(frappe.local, "login_manager", login_manager, create=True),
		):
			_accept_invitation(key, False)
		login_manager.login_as.assert_not_called()
		self.assertEqual(frappe.local.response.location, frappe.utils.get_url("/abc"))
		self.assertIn("System Manager", frappe.get_roles(user.name))
		self.assertFalse(frappe.db.get_value("User", user.name, "reset_password_key"))

	def test_get_pending_invitations_api(self):
		invitation = self.get_dummy_invitation()
		invitation.insert()
		invitation.reload()
		pending_invitations = get_pending_invitations("frappe")
		self.assertEqual(len(pending_invitations), 1)
		pending_invitation = pending_invitations[0]
		self.assertEqual(pending_invitation["name"], invitation.name)
		self.assertEqual(pending_invitation["email"], invitation.email)
		roles = pending_invitation["roles"]
		self.assertIsInstance(roles, list)
		self.assertSequenceEqual(roles, [r.role for r in invitation.roles])

	def test_cancel_invitation_api(self):
		invitation = self.get_dummy_invitation()
		invitation.insert()
		frappe.db.commit()

		invitation.reload()
		self.assertEqual(invitation.status, "Pending")
		self.assertEqual(len(self.get_email_names()), 1)
		res = cancel_invitation(invitation.name, "frappe")
		frappe.db.commit()

		self.assertTrue(res["cancelled_now"])
		invitation.reload()
		self.assertEqual(invitation.status, "Cancelled")
		self.assertEqual(len(self.get_email_names()), 2)
		res = cancel_invitation(invitation.name, "frappe")
		frappe.db.commit()

		self.assertFalse(res["cancelled_now"])
		self.assertEqual(len(self.get_email_names()), 2)

	def get_dummy_invitation(self):
		return frappe.get_doc(
			doctype="User Invitation",
			email=emails[1],
			roles=[dict(role="System Manager")],
			redirect_to_path="/abc",
			app_name="frappe",
		)

	def get_email_names(self, sent_only=True):
		filters = {"status": "Sent"} if sent_only else None
		return frappe.db.get_all("Email Queue", filters=filters, fields=["name"])

	def get_email_messages(self, sent_only=True):
		filters = {"status": "Sent"} if sent_only else None
		return frappe.db.get_all("Email Queue", filters=filters, fields=["message"])
