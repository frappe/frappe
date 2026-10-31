# Copyright (c) 2025, Frappe Technologies and Contributors
# See license.txt

import re
from unittest.mock import patch

import frappe
import frappe.utils
from frappe.core.api.user_invitation import (
	_accept_invitation,
	cancel_invitation,
	get_invited_emails,
	get_pending_invitations,
	invite_by_email,
	resend_invitation,
)
from frappe.core.doctype.user_invitation.user_invitation import UserInvitation, mark_expired_invitations
from frappe.handler import run_doc_method
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
		frappe.set_user("Administrator")
		for user_email in emails:
			if frappe.db.exists("User", user_email):
				frappe.delete_doc("User", user_email)
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
		original_disable_user_pass_login = frappe.get_system_settings("disable_user_pass_login")
		frappe.db.set_single_value("System Settings", "disable_user_pass_login", 1)
		self.assertEqual(len(self.get_email_names(False)), 1)
		key = invitation.send_invitation_mail()
		self.assertEqual(len(self.get_email_names(False)), 2)
		_accept_invitation(key, True)
		frappe.db.set_single_value(
			"System Settings", "disable_user_pass_login", original_disable_user_pass_login
		)
		res = frappe.local.response
		self.assertEqual(res.type, "redirect")
		pattern = f"^{re.escape(frappe.utils.get_url(''))}/abc$"
		self.assertRegex(res.location, pattern)
		user = frappe.get_doc("User", invitation.email)
		IntegrationTestUserInvitation.delete_invitation(invitation.name)
		frappe.delete_doc("User", user.name)

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

	def test_resend_invite_needs_write(self):
		invitation = self.insert_invitation_without_mail()
		self.addCleanup(setattr, frappe.local, "request", getattr(frappe.local, "request", None))
		frappe.local.request = frappe._dict(method="POST")
		reader = self.make_user("invitation-reader@example.com")
		writer = self.make_user("invitation-writer@example.com")
		frappe.share.add("User Invitation", invitation.name, reader, read=1, write=0)
		frappe.share.add("User Invitation", invitation.name, writer, read=1, write=1)

		frappe.set_user(reader)
		with patch.object(UserInvitation, "send_invitation_mail") as send:
			self.assertRaises(
				frappe.PermissionError,
				run_doc_method,
				"resend_invite",
				dt="User Invitation",
				dn=invitation.name,
			)
		send.assert_not_called()

		frappe.set_user(writer)
		with patch.object(UserInvitation, "send_invitation_mail") as send:
			run_doc_method("resend_invite", dt="User Invitation", dn=invitation.name)
		send.assert_called_once()

	def test_resend_invitation_api_works_for_an_app_role_without_write(self):
		role = "Test Invitation Manager"
		frappe.get_doc(doctype="Role", role_name=role, desk_access=1).insert(ignore_if_duplicate=True)
		manager = self.make_user("invitation-manager@example.com", role)
		invitation = self.insert_invitation_without_mail()

		frappe.set_user(manager)
		with (
			self.patch_inviter_role(role),
			patch.object(UserInvitation, "send_invitation_mail") as send,
		):
			resend_invitation(invitation.name, "frappe")
		send.assert_called_once()

	def test_reads_work_for_an_app_inviter_without_a_docperm(self):
		role = "Test Invitation Manager"
		frappe.get_doc(doctype="Role", role_name=role, desk_access=1).insert(ignore_if_duplicate=True)
		manager = self.make_user("invitation-manager@example.com", role)
		pending = self.insert_invitation_without_mail(emails[1])
		self.insert_invitation_without_mail(emails[2]).db_set("status", "Accepted")
		self.insert_invitation_without_mail(emails[3]).db_set("status", "Cancelled")

		frappe.set_user(manager)
		with self.patch_inviter_role(role):
			self.assertFalse(frappe.has_permission("User Invitation", "read"))
			self.assertEqual(
				get_pending_invitations("frappe"),
				[{"name": pending.name, "email": emails[1], "roles": ["System Manager"]}],
			)
			self.assertCountEqual(
				get_invited_emails("frappe", frappe.as_json(emails[1:5])), [emails[1], emails[2]]
			)

	def test_reads_refuse_a_user_who_cannot_invite(self):
		outsider = self.make_user("invitation-outsider@example.com", "Blogger")
		self.insert_invitation_without_mail(emails[1])

		frappe.set_user(outsider)
		with self.patch_inviter_role("Test Invitation Manager"):
			self.assertRaises(frappe.PermissionError, get_pending_invitations, "frappe")
			self.assertRaises(frappe.PermissionError, get_invited_emails, "frappe", [emails[1]])

	def patch_inviter_role(self, role: str):
		get_hooks = frappe.get_hooks

		def hooks_with_role(hook=None, *args, **kwargs):
			if hook == "user_invitation":
				return {"allowed_roles": {role: []}}
			return get_hooks(hook, *args, **kwargs)

		return patch("frappe.get_hooks", hooks_with_role)

	def make_user(self, email: str, *roles: str) -> str:
		user = frappe.get_doc(doctype="User", email=email, first_name=email, send_welcome_email=0)
		user.append_roles(*roles)
		user.insert(ignore_if_duplicate=True)
		self.addCleanup(frappe.set_user, frappe.session.user)
		self.addCleanup(frappe.delete_doc, "User", email, force=True)
		self.addCleanup(frappe.set_user, "Administrator")
		return email

	def insert_invitation_without_mail(self, email: str = emails[1]):
		with patch.object(UserInvitation, "send_invitation_mail"):
			return self.get_dummy_invitation(email).insert()

	def get_dummy_invitation(self, email: str = emails[1]):
		return frappe.get_doc(
			doctype="User Invitation",
			email=email,
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
