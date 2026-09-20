# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.core.doctype.user.passkey import (
	enrolling_user,
	get_passkeys,
	link_allows_passkey,
	parse_credential,
	pop_challenge,
	remove_passkey,
	rename_passkey,
	stash_challenge,
	transport_hints,
	transports_to_store,
)
from frappe.core.doctype.user.user import get_redirect_url_for_user
from frappe.tests import IntegrationTestCase
from frappe.utils.password import get_decrypted_password

TEST_ROLE = "_Test Passkey Role"

OWNER = "passkey_owner@example.com"
PEER = "passkey_peer@example.com"
MANAGER = "passkey_manager@example.com"


class TestUserPasskey(IntegrationTestCase):
	"""Stored credentials are reachable through the passkey APIs, not through DocPerms.

	The doctype grants read/delete to System Manager alone and create/write to nobody,
	so an ordinary user gets at their own passkeys only via `get_passkeys` /
	`remove_passkey`, which enforce owner-or-System-Manager themselves.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("Role", TEST_ROLE):
			frappe.get_doc({"doctype": "Role", "role_name": TEST_ROLE, "desk_access": 1}).insert(
				ignore_permissions=True
			)

		for email, roles in ((OWNER, [TEST_ROLE]), (PEER, [TEST_ROLE]), (MANAGER, ["System Manager"])):
			if not frappe.db.exists("User", email):
				user = frappe.new_doc("User")
				user.update({"email": email, "first_name": email.split("@")[0], "send_welcome_email": 0})
				for role in roles:
					user.append("roles", {"role": role})
				user.insert(ignore_permissions=True)

	def make_passkey(self, user, credential_id, **kwargs):
		doc = frappe.get_doc(
			{
				"doctype": "User Passkey",
				"user": user,
				"label": "test",
				"rp_id": "localhost",
				"credential_id": credential_id,
				"public_key": "cGs=",
				"sign_count": 0,
				**kwargs,
			}
		)
		doc.insert(ignore_permissions=True)
		return doc

	def stored_public_key(self, name):
		"""The key as it actually lives in __Auth, or None once it is gone."""
		return get_decrypted_password("User Passkey", name, "public_key", raise_exception=False)

	def enrollment_key(self, user):
		"""The raw key out of a freshly generated reset link."""
		link = frappe.get_doc("User", user)._reset_password()
		return link.split("key=")[1].split("&")[0]

	def test_owner_is_the_passkey_user_not_the_session(self):
		# enrollment from an email link runs as Guest - the credential grants the session,
		# so there is no session yet when the row is written
		with self.set_user("Guest"):
			doc = self.make_passkey(OWNER, "cred-enrolled-as-guest")

		self.assertEqual(doc.owner, OWNER)
		self.assertEqual(frappe.db.get_value("User Passkey", doc.name, "owner"), OWNER)

	def test_api_gives_a_user_only_their_own(self):
		mine = self.make_passkey(OWNER, "cred-mine")
		theirs = self.make_passkey(PEER, "cred-theirs")

		with self.set_user(OWNER):
			listed = {row.name for row in get_passkeys(OWNER)}
			self.assertIn(mine.name, listed)
			self.assertNotIn(theirs.name, listed)

			self.assertRaises(frappe.PermissionError, get_passkeys, PEER)
			self.assertRaises(frappe.PermissionError, remove_passkey, theirs.name)

			remove_passkey(mine.name)

		self.assertFalse(frappe.db.exists("User Passkey", mine.name))

	def test_api_lets_a_system_manager_reach_anyone(self):
		theirs = self.make_passkey(PEER, "cred-for-manager")

		with self.set_user(MANAGER):
			self.assertIn(theirs.name, {row.name for row in get_passkeys(PEER)})
			remove_passkey(theirs.name)

		self.assertFalse(frappe.db.exists("User Passkey", theirs.name))

	def test_docperms_grant_nothing_to_an_ordinary_user(self):
		existing = self.make_passkey(OWNER, "cred-existing")

		with self.set_user(OWNER):
			for ptype in ("read", "write", "delete"):
				self.assertFalse(frappe.has_permission("User Passkey", ptype, doc=existing.name))
			self.assertFalse(frappe.has_permission("User Passkey", "create"))

	def test_nobody_may_create_or_write_even_as_system_manager(self):
		existing = self.make_passkey(OWNER, "cred-existing-manager")

		with self.set_user(MANAGER):
			self.assertFalse(frappe.has_permission("User Passkey", "create"))
			self.assertFalse(frappe.has_permission("User Passkey", "write", doc=existing.name))
			# read and delete are the two it does hold
			self.assertTrue(frappe.has_permission("User Passkey", "read", doc=existing.name))
			self.assertTrue(frappe.has_permission("User Passkey", "delete", doc=existing.name))

	def test_deleting_a_user_takes_their_passkeys(self):
		victim = "passkey_deleted@example.com"
		if not frappe.db.exists("User", victim):
			user = frappe.new_doc("User")
			user.update({"email": victim, "first_name": "deleted", "send_welcome_email": 0})
			user.insert(ignore_permissions=True)

		passkey = self.make_passkey(victim, "cred-of-deleted-user")
		self.assertEqual(self.stored_public_key(passkey.name), "cGs=")

		frappe.delete_doc("User", victim, ignore_permissions=True, force=True)

		self.assertFalse(frappe.db.exists("User Passkey", passkey.name))
		# the public key lives in __Auth, which deleting the rows directly would orphan
		self.assertIsNone(self.stored_public_key(passkey.name))

	def test_get_passkeys_reports_the_backup_flags(self):
		synced = self.make_passkey(OWNER, "cred-synced", multi_device=1, backed_up=1)
		device_bound = self.make_passkey(OWNER, "cred-device-bound")

		with self.set_user(OWNER):
			rows = {row.name: row for row in get_passkeys(OWNER)}

		self.assertEqual((rows[synced.name].multi_device, rows[synced.name].backed_up), (1, 1))
		self.assertEqual((rows[device_bound.name].multi_device, rows[device_bound.name].backed_up), (0, 0))

	def test_a_long_credential_id_is_storable(self):
		# base64url of a large credential id - the column used to cap at 140 chars
		doc = self.make_passkey(OWNER, "c" * 400)
		self.assertEqual(len(frappe.db.get_value("User Passkey", doc.name, "credential_id")), 400)

	def test_sign_count_holds_the_whole_uint32_range(self):
		doc = self.make_passkey(OWNER, "cred-big-counter", sign_count=2**32 - 1)
		self.assertEqual(frappe.db.get_value("User Passkey", doc.name, "sign_count"), 2**32 - 1)

	def test_stored_transports_keep_only_known_values(self):
		hostile = {"response": {"transports": ["usb", "nfc", "made-up", 1, None, {"a": 1}, "x" * 500]}}
		self.assertEqual(transports_to_store(hostile), "usb, nfc")

		# and whatever is stored has to survive the trip back out as enum members
		self.assertEqual([t.value for t in transport_hints(transports_to_store(hostile))], ["usb", "nfc"])

		for shape in ({}, {"response": "not a dict"}, {"response": {"transports": "usb"}}):
			self.assertEqual(transports_to_store(shape), "")

	def test_a_credential_that_is_not_an_object_is_refused(self):
		for payload in ("not json", '"a string"', "123", "null", "[1, 2]", ""):
			self.assertRaises(frappe.ValidationError, parse_credential, payload)

		self.assertEqual(parse_credential('{"id": "abc"}'), {"id": "abc"})

	def test_a_guest_session_cannot_enroll_without_a_link(self):
		with self.set_user("Guest"):
			self.assertRaises(frappe.PermissionError, enrolling_user, None)

	def test_only_a_desk_issued_link_may_enroll_a_passkey(self):
		# a forgot-password link is requested by Guest: it sets a password, nothing else
		with self.set_user("Guest"):
			self.assertFalse(link_allows_passkey(self.enrollment_key(OWNER)))

		# nor can any logged-in user upgrade someone else's link by asking for one
		with self.set_user(PEER):
			self.assertFalse(link_allows_passkey(self.enrollment_key(OWNER)))

		# a System Manager holds write on the user, so their link carries the right
		with self.set_user(MANAGER):
			self.assertTrue(link_allows_passkey(self.enrollment_key(OWNER)))

		# and so does a user asking for their own
		with self.set_user(OWNER):
			self.assertTrue(link_allows_passkey(self.enrollment_key(OWNER)))

	def test_an_unknown_key_allows_nothing(self):
		self.assertFalse(link_allows_passkey("not-a-real-key"))
		self.assertFalse(link_allows_passkey(None))

	def test_where_a_link_enrollment_lands_the_user(self):
		# a Website User is sent to the portal, and keeps their own redirect
		self.assertEqual(get_redirect_url_for_user("/somewhere", "Website User"), "/somewhere")

		# a System User belongs in the desk whatever the stored redirect says
		self.assertNotEqual(get_redirect_url_for_user("/somewhere", "System User"), "/somewhere")

	def test_a_challenge_is_single_use(self):
		state = stash_challenge(b"chal", "login", "Guest")

		self.assertEqual(pop_challenge(state, "login", "Guest"), b"chal")
		self.assertRaises(frappe.ValidationError, pop_challenge, state, "login", "Guest")

	def test_a_challenge_is_bound_to_its_ceremony(self):
		state = stash_challenge(b"chal", "register", OWNER)

		# a registration challenge cannot be spent on login, and the attempt burns it:
		# redemption is single use even when it fails, so a mismatch cannot be probed
		self.assertRaises(frappe.ValidationError, pop_challenge, state, "login", OWNER)
		self.assertRaises(frappe.ValidationError, pop_challenge, state, "register", OWNER)

	def test_a_challenge_is_bound_to_its_user(self):
		state = stash_challenge(b"chal", "register", OWNER)

		self.assertRaises(frappe.ValidationError, pop_challenge, state, "register", PEER)

	def test_an_unknown_state_is_refused(self):
		self.assertRaises(frappe.ValidationError, pop_challenge, "no-such-state", "login", "Guest")

	def test_only_the_owner_may_rename(self):
		mine = self.make_passkey(OWNER, "cred-to-rename")
		theirs = self.make_passkey(PEER, "cred-of-a-peer")

		with self.set_user(OWNER):
			rename_passkey(mine.name, "MacBook Touch ID")
			self.assertRaises(frappe.PermissionError, rename_passkey, theirs.name, "stolen")

		# stricter than read and delete: a System Manager reaches those, not this
		with self.set_user(MANAGER):
			self.assertRaises(frappe.PermissionError, rename_passkey, theirs.name, "by a manager")
			self.assertTrue(get_passkeys(PEER))
			remove_passkey(theirs.name)

		self.assertEqual(frappe.db.get_value("User Passkey", mine.name, "label"), "MacBook Touch ID")
		self.assertFalse(frappe.db.exists("User Passkey", theirs.name))

	def test_a_rename_is_held_to_the_label_rules(self):
		doc = self.make_passkey(OWNER, "cred-rename-rules")

		with self.set_user(OWNER):
			# mandatory, and html is stripped the way it is on enrollment
			self.assertRaises(frappe.MandatoryError, rename_passkey, doc.name, "")
			rename_passkey(doc.name, "<script>alert(1)</script>Phone")

		self.assertEqual(frappe.db.get_value("User Passkey", doc.name, "label"), "Phone")
