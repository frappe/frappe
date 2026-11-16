# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import unicodedata
from unittest.mock import patch

from cryptography.fernet import Fernet

import frappe
from frappe.auth import LoginManager
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import change_settings
from frappe.utils.password import (
	MAX_PASSWORD_SIZE,
	Auth,
	check_password,
	decrypt,
	encrypt,
	passlibctx,
	set_admin_password_login_setting,
	update_password,
)


class TestPassword(IntegrationTestCase):
	def setUp(self):
		frappe.delete_doc("Email Account", "Test Email Account Password")
		frappe.delete_doc("Email Account", "Test Email Account Password-new")

	def test_encrypted_password(self):
		doc = self.make_email_account()

		new_password = "test-password"
		doc.password = new_password
		doc.save()

		self.assertEqual(doc.password, "*" * len(new_password))

		password_list = get_password_list(doc)

		auth_password = password_list[0].get("password", "")

		# encrypted
		self.assertTrue(auth_password != new_password)

		# decrypted
		self.assertEqual(doc.get_password(), new_password)

		return doc, new_password

	def make_email_account(self, name="Test Email Account Password"):
		if not frappe.db.exists("Email Account", name):
			return frappe.get_doc(
				{
					"doctype": "Email Account",
					"domain": "example.com",
					"email_account_name": name,
					"append_to": "Communication",
					"smtp_server": "test.example.com",
					"pop3_server": "pop.test.example.com",
					"email_id": "test-password@example.com",
					"password": "password",
				}
			).insert()

		else:
			return frappe.get_doc("Email Account", name)

	def test_hashed_password(self, user="test@example.com"):
		old_password = "Eastern_43A1W"
		new_password = "Eastern_43A1W-new"

		update_password(user, new_password)

		auth = get_password_list(dict(doctype="User", name=user))[0]

		# is not plain text
		self.assertTrue(auth.password != new_password)

		# is valid hashing
		self.assertTrue(passlibctx.verify(new_password, auth.password))

		self.assertTrue(check_password(user, new_password))

		# revert back to old
		update_password(user, old_password)
		self.assertTrue(check_password(user, old_password))

		# shouldn't work with old password
		self.assertRaises(frappe.AuthenticationError, check_password, user, new_password)

	def test_unicode_password_normalized(self, user="test@example.com"):
		nfc = "Caf\u00e9_43A1W"
		nfd = unicodedata.normalize("NFD", nfc)

		update_password(user, nfd)
		self.assertTrue(check_password(user, nfc))
		self.assertTrue(check_password(user, nfd))

		# old hash of raw NFD text logs in as before, then gets rehashed normalized
		set_raw_hash(user, nfd)
		self.assertTrue(check_password(user, nfd))

		stored = get_password_list(dict(doctype="User", name=user))[0].password
		self.assertTrue(passlibctx.verify(nfc, stored))
		self.assertFalse(passlibctx.verify(nfd, stored))

		self.assertRaises(frappe.AuthenticationError, check_password, user, "Cafe_43A1W")
		update_password(user, "Eastern_43A1W")

	def test_oversized_password(self):
		user = "test@example.com"
		too_long = "a" * (MAX_PASSWORD_SIZE + 1)
		self.assertRaises(frappe.ValidationError, update_password, user, too_long)
		# check paths: same error, not an AuthenticationError the login manager would swallow
		self.assertRaises(frappe.ValidationError, check_password, user, too_long)
		self.assertRaises(frappe.ValidationError, check_password, user, "a" * 5000)

		from frappe.core.doctype.user.user import update_password as update_password_api

		with self.assertRaisesRegex(frappe.ValidationError, "^New Password size"):
			update_password_api(new_password=too_long, old_password="Eastern_43A1W")
		with self.assertRaisesRegex(frappe.ValidationError, "^Old Password size"):
			update_password_api(new_password="Eastern_43A1W", old_password=too_long)

		# login: same error whether or not the account exists, so no enumeration
		login_manager = object.__new__(LoginManager)  # skip __init__, it needs a request
		for usr in (user, "no-such-user@example.com"):
			self.assertRaises(frappe.ValidationError, login_manager.authenticate, usr, too_long)

	def test_password_on_rename_user(self):
		password = "test-rename-password"

		doc = self.make_email_account()
		doc.password = password
		doc.save()

		old_name = doc.name
		new_name = old_name + "-new"
		frappe.rename_doc(doc.doctype, old_name, new_name)

		new_doc = frappe.get_doc(doc.doctype, new_name)
		self.assertEqual(new_doc.get_password(), password)
		self.assertTrue(not get_password_list(doc))

		frappe.rename_doc(doc.doctype, new_name, old_name)
		self.assertTrue(get_password_list(doc))

	def test_password_on_delete(self):
		doc = self.make_email_account()
		doc.delete()

		self.assertTrue(not get_password_list(doc))

	def test_password_unset(self):
		doc = self.make_email_account()

		doc.password = "asdf"
		doc.save()
		self.assertEqual(doc.get_password(raise_exception=False), "asdf")

		doc.password = ""
		doc.save()
		self.assertEqual(doc.get_password(raise_exception=False), None)

	def test_no_administrator_password_while_disabled(self):
		before = frappe.get_system_settings("disable_admin_pass_login")
		set_admin_password_login_setting(1)
		self.addCleanup(set_admin_password_login_setting, before)

		frappe.set_user("test@example.com")
		self.addCleanup(frappe.set_user, "Administrator")

		self.assertRaises(
			frappe.PasswordLoginDisabledError, update_password, "Administrator", "new-admin-pwd"
		)
		# other users are not affected
		update_password("test@example.com", "new-test-pwd")
		self.assertEqual(check_password("test@example.com", "new-test-pwd"), "test@example.com")

	def test_bench_add_user_skips_password_while_login_disabled(self):
		from frappe.commands.site import add_new_user

		email = frappe.generate_hash() + "@example.com"
		self.addCleanup(frappe.delete_doc, "User", email, force=True, ignore_missing=True)

		with (
			change_settings("System Settings", disable_user_pass_login=1, login_with_email_link=1),
			patch("frappe.utils.password.click.secho") as secho,
		):
			add_new_user(email, password="Eastern_43A1W", role=())

		# user made, password skipped, warning shown
		self.assertTrue(frappe.db.exists("User", email))
		self.assertFalse(get_password_list(dict(doctype="User", name=email)))
		secho.assert_called_once()

	def test_new_site_admin_password(self):
		from frappe.core.doctype.system_settings.system_settings import clear_system_settings_cache
		from frappe.utils.install import setup_admin_password

		self.addCleanup(clear_system_settings_cache)
		self.addCleanup(frappe.db.rollback)
		admin_row = (Auth.doctype == "User") & (Auth.name == "Administrator") & (Auth.fieldname == "password")

		# no password given: nothing stored, password login stays disabled
		set_admin_password_login_setting(1)
		frappe.qb.from_(Auth).delete().where(admin_row).run()
		with patch.dict(frappe.conf, {"admin_password": None}):
			setup_admin_password()
		self.assertEqual(frappe.get_system_settings("disable_admin_pass_login"), 1)
		self.assertFalse(frappe.qb.from_(Auth).select(Auth.password).where(admin_row).run())

		# password given: stored, and password login turned back on
		with patch.dict(frappe.conf, {"admin_password": "Eastern_43A1W"}):
			setup_admin_password()
		self.assertEqual(frappe.get_system_settings("disable_admin_pass_login"), 0)
		self.assertEqual(frappe.db.get_default("disable_admin_pass_login"), "0")
		self.assertEqual(check_password("Administrator", "Eastern_43A1W"), "Administrator")

	def test_custom_encryption_key(self):
		text = "Frappe Framework"
		custom_encryption_key = Fernet.generate_key().decode()

		encrypted_text = encrypt(text, encryption_key=custom_encryption_key)
		decrypted_text = decrypt(encrypted_text, encryption_key=custom_encryption_key)

		self.assertEqual(text, decrypted_text)

		pass


def get_password_list(doc):
	return frappe.db.sql(
		"""SELECT `password`
			FROM `__Auth`
			WHERE `doctype`=%s
			AND `name`=%s
			AND `fieldname`='password' LIMIT 1""",
		(doc.get("doctype"), doc.get("name")),
		as_dict=1,
	)


def set_raw_hash(user, pwd):
	"""Stores a hash of pwd as-is, like before normalization."""
	frappe.qb.update(Auth).set(Auth.password, passlibctx.hash(pwd)).where(
		(Auth.doctype == "User") & (Auth.name == user) & (Auth.fieldname == "password")
	).run()
