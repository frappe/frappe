# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals
import frappe
import unittest
import os
from frappe.integrations.doctype.ldap_settings import ldap_settings
from frappe import get_doc, ValidationError, _
from unittest.mock import MagicMock, patch
import sys
import ldap3
import ssl

TEST_EMAIL = 'billy@test.com'


def set_dummy_ldap_settings(settings):
	settings.ldap_server_url = "ldap://whatever.whatever:389"
	settings.organizational_unit = "something"
	settings.base_dn = "whatever"
	settings.password = "hioooo"
	settings.ldap_search_string = "sid={0}"
	settings.ldap_first_name_field = "first_name"
	settings.ldap_email_field = "email"
	settings.ldap_username_field = "username"
	settings.default_role = "Blogger"
	settings.enabled = True



class TestNoLDAP3ModuleTests(unittest.TestCase):
	def setUp(self):
		super().setUp()
		self.tmpldap = sys.modules['ldap3']
		sys.modules['ldap3'] = None


	def tearDown(self):
		sys.modules['ldap3'] = self.tmpldap

	def test_connect_to_ldap_throws_validation_error_when_ldap3_not_found(self):
		with self.assertRaises(ValidationError) as cm:
			settings = get_doc("LDAP Settings")
			set_dummy_ldap_settings(settings)
			settings.connect_to_ldap("test", "test")
		self.assertEqual('Please Install the ldap3 library via pip to use ldap functionality.',
		                 str(cm.exception))



class TestLDAPSettings(unittest.TestCase):

	def setUp(self):
		pass


	def tearDown(self):
		settings = get_doc("LDAP Settings")
		if settings:
			settings.delete()






	def test_validation_ldap_search_string_needs_to_contain_a_placeholder_for_format(self):
		with self.assertRaises(ValidationError) as cm:
			settings = get_doc("LDAP Settings")
			set_dummy_ldap_settings(settings)
			settings.ldap_search_string = 'notvalid'
			settings.save()
		self.assertEqual("LDAP Search String needs to end with a placeholder, eg sAMAccountName={0}",
			                 str(cm.exception))


	def test_validation_enabling_ldap_must_try_to_connect_to_ldap(self):
		with patch("frappe.integrations.doctype.ldap_settings.ldap_settings.LDAPSettings.connect_to_ldap") as mocked_connect_to_ldap:
			settings = get_doc("LDAP Settings")
			set_dummy_ldap_settings(settings)
			settings.enabled = True
			settings.save()
			mocked_connect_to_ldap.assert_called_once()

	def test_validation_enabling_ldap_must_test_for_connection_and_not_save_when_errors(self):
		with patch("frappe.integrations.doctype.ldap_settings.ldap_settings.LDAPSettings.connect_to_ldap",
		           side_effect=OSError('boom')) as mocked_connect_to_ldap:
			settings = get_doc("LDAP Settings")
			set_dummy_ldap_settings(settings)
			settings.enabled = True
			with self.assertRaises(OSError) as cm:
				settings.save()

	def test_connect_to_ldap_catches_any_other_error(self):
		with patch("ldap3.Connection",
		           side_effect=IOError("blah")):
			with self.assertRaises(ValidationError) as cm:
				settings = get_doc("LDAP Settings")
				set_dummy_ldap_settings(settings)
				settings.connect_to_ldap("test", "test")

	def test_connect_to_ldap_cert_required_if_trusted_cert_set(self):
		with patch("ldap3.Server", autospec=True, create=True) as mm_server:
			with patch("ldap3.Connection") as mm_connection:
				settings = get_doc("LDAP Settings")
				set_dummy_ldap_settings(settings)
				settings.require_trusted_certificate = "Yes"
				settings.local_ca_certs_file = None
				settings.local_server_certificate_file = None
				settings.local_private_key_file = None
				settings.connect_to_ldap("test", "test")

				assert (mm_server.call_args[1]["tls"].validate == ssl.CERT_REQUIRED)

	def test_connect_to_ldap_cert_ignored_if_trusted_cert_not_set(self):
		with patch("ldap3.Server", autospec=True, create=True) as mm_server:
			with patch("ldap3.Connection") as mm_connection:
				settings = get_doc("LDAP Settings")
				set_dummy_ldap_settings(settings)
				settings.require_trusted_certificate = "No"
				settings.local_ca_certs_file = None
				settings.local_server_certificate_file = None
				settings.local_private_key_file = None
				settings.connect_to_ldap("test", "test")

				assert (mm_server.call_args[1]["tls"].validate == ssl.CERT_NONE)

	def test_connect_to_ldap_cert_path_to_key_files_correctly_set(self):
		with patch("ldap3.Server", autospec=True, create=True) as mm_server:
			with patch("ldap3.Connection") as mm_connection:
				settings = get_doc("LDAP Settings")
				set_dummy_ldap_settings(settings)
				settings.require_trusted_certificate = "Yes"
				settings.local_ca_certs_file = "/path/to/cacerts.pem"
				settings.local_server_certificate_file = "/path/to/server.pem"
				settings.local_private_key_file = "/path/to/priv.pem"
				settings.connect_to_ldap("test", "test")
				assert (mm_server.call_args[1]["tls"].ca_certs_file == "/path/to/cacerts.pem")
				assert (mm_server.call_args[1]["tls"].private_key_file == "/path/to/priv.pem")
				assert (mm_server.call_args[1]["tls"].certificate_file == "/path/to/server.pem")

	def test_connect_to_ldap_do_tls_connection_before_binding_if_tls(self):
		with patch("ldap3.Server", autospec=True, create=True) as mm_server:
			with patch("ldap3.Connection") as mm_connection:
				settings = get_doc("LDAP Settings")
				set_dummy_ldap_settings(settings)
				settings.ssl_tls_mode = "StartTLS"
				settings.connect_to_ldap("test", "test")

				assert (mm_connection.call_args[1]["auto_bind"] == ldap3.AUTO_BIND_TLS_BEFORE_BIND)

	def test_authenticating_ldap_user_only_when_enabled(self):
		settings = get_doc("LDAP Settings")
		set_dummy_ldap_settings(settings)
		settings.enabled = False
		with patch("frappe.get_doc") as mm_get_doc:
			mm_get_doc.return_value = settings
			with self.assertRaises(ValidationError) as cm:
				settings.authenticate("test", "test")
			self.assertEqual("LDAP is not enabled.",str(cm.exception))

	def test_authenticating_ldap_user_throws_not_valid_user_when_search_not_found(self):
		settings = get_doc("LDAP Settings")
		set_dummy_ldap_settings(settings)
		with patch("frappe.get_doc") as mm_get_doc:
			mm_get_doc.return_value = settings
			with patch(
					"frappe.integrations.doctype.ldap_settings.ldap_settings.LDAPSettings.connect_to_ldap") as mm_conn_ldap:
				mocked_server = MagicMock()
				mm_conn_ldap.return_value = mocked_server
				mocked_server.entries = []
				with self.assertRaises(ValidationError) as cm:
					settings.authenticate("test", "test")
				self.assertEqual("Invalid username or password",str(cm.exception))

	def test_authenticating_ldap_user_creates_user_if_not_in_database(self):
		with patch(
				"frappe.integrations.doctype.ldap_settings.ldap_settings.LDAPSettings.connect_to_ldap") as mm_conn_ldap:
			new_user_email = TEST_EMAIL
			new_user_first_name = 'Billy'
			new_user_username = 'bill'

			new_role = get_doc({
				"doctype": "Role",
				"role_name": "Test Role"})
			new_role.insert()

			settings = get_doc("LDAP Settings")
			settings.ldap_email_field = "email"
			settings.ldap_username_field = "username"
			settings.ldap_first_name_field = "first_name"
			settings.ldap_search_string = "cn={0}"
			settings.organizational_unit = "ou=test,o=lab"
			settings.ldap_server_url = "test"
			settings.base_dn = "test"
			settings.password = "whatever"
			settings.default_role = new_role.name
			settings.ldap_group_field = "memberOf"
			settings.enabled = True
			settings.save()

			server = ldap3.Server('my_fake_server')
			connection = ldap3.Connection(server,
			                              user='cn=bill,ou=test,o=lab',
			                              password='my_password',
			                              client_strategy=ldap3.MOCK_SYNC)
			connection.strategy.add_entry("cn={0},ou=test,o=lab".format(new_user_username),
			                              {"first_name": new_user_first_name,
			                               "email": new_user_email,
			                               "username": new_user_username,
			                               "memberOf": 'cn=testgroup,ou=test,o=lab'
			                               })
			connection.bind()

			mm_conn_ldap.return_value = connection
			assert (not frappe.db.exists("User", new_user_email))
			settings.authenticate(new_user_username,
			                      "whatever")
			assert (frappe.db.exists("User", new_user_email))
			new_user = get_doc("User",
			                   new_user_email)

			assert (new_user.first_name == new_user_first_name)
			assert (new_user.username == new_user_username)
			assert (new_user.email == new_user_email)
			current_roles = [d.role for d in new_user.get("roles")]
			assert (settings.default_role in current_roles)

	def test_authenticating_ldap_user_with_no_group_field_creates_user_if_not_in_database(self):
		with patch(
				"frappe.integrations.doctype.ldap_settings.ldap_settings.LDAPSettings.connect_to_ldap") as mm_conn_ldap:
			new_user_email = TEST_EMAIL
			new_user_first_name = 'Billy'
			new_user_username = 'bill'

			new_role = get_doc({
				"doctype": "Role",
				"role_name": "Test Role"})
			new_role.insert()

			settings = get_doc("LDAP Settings")
			settings.ldap_email_field = "email"
			settings.ldap_username_field = "username"
			settings.ldap_first_name_field = "first_name"
			settings.ldap_search_string = "cn={0}"
			settings.organizational_unit = "ou=test,o=lab"
			settings.ldap_server_url = "test"
			settings.base_dn = "test"
			settings.password = "whatever"
			settings.default_role = new_role.name
			# settings.ldap_group_field = "memberOf"
			settings.enabled = True
			settings.save()

			server = ldap3.Server('my_fake_server')
			connection = ldap3.Connection(server,
			                              user='cn=bill,ou=test,o=lab',
			                              password='my_password',
			                              client_strategy=ldap3.MOCK_SYNC)
			connection.strategy.add_entry("cn={0},ou=test,o=lab".format(new_user_username),
			                              {"first_name": new_user_first_name,
			                               "email": new_user_email,
			                               "username": new_user_username,
			                               # "memberOf": 'cn=testgroup,ou=test,o=lab'
			                               })
			connection.bind()

			mm_conn_ldap.return_value = connection
			assert (not frappe.db.exists("User", new_user_email))
			settings.authenticate(new_user_username,
			                      "whatever")
			assert (frappe.db.exists("User", new_user_email))
			new_user = get_doc("User",
			                   new_user_email)

			assert (new_user.first_name == new_user_first_name)
			assert (new_user.username == new_user_username)
			assert (new_user.email == new_user_email)
			current_roles = [d.role for d in new_user.get("roles")]
			assert (settings.default_role in current_roles)

	def test_role_sync_removes_role_mapped(self):
		r1 = get_doc({
			"doctype": "Role",
			"role_name": "Test Role 1"})
		r1.insert()
		r2 = get_doc({
			"doctype": "Role",
			"role_name": "Test Role 2"})
		r2.insert()

		settings = get_doc("LDAP Settings")
		set_dummy_ldap_settings(settings)

		settings.append("ldap_groups", {
			"ldap_group": "cn=Group1",
			"erpnext_role": "Test Role 1"
		})
		settings.append("ldap_groups", {
			"ldap_group": "cn=group2",
			"erpnext_role": "Test Role 2"
		})

		user = {
			"doctype": "User",
			"first_name": "bill",
			"email": "bill@test.com",
			"username": "bill",
			"send_welcome_email": 0,
			"language": "",
			"user_type": "System User",
			"roles": [{
				"role": _("Blogger")
			}, {"role": "Test Role 2"}]
		}

		# insert the existing user.
		the_user = get_doc(user).insert(ignore_permissions=True)

		settings.sync_roles(the_user, ['cn=group1'])

		found_roles = [d.role for d in the_user.get("roles")]

		assert ('Blogger' in found_roles and 'Test Role 1' in found_roles and settings.default_role in found_roles)

	def test_role_sync_correctly_adds_roles(self):
		r1 = get_doc({
			"doctype": "Role",
			"role_name": "Test Role 1"})
		r1.insert()
		r2 = get_doc({
			"doctype": "Role",
			"role_name": "Test Role 2"})
		r2.insert()
		r3 = get_doc({
			"doctype": "Role",
			"role_name": "Test Role 3"})
		r3.insert()

		settings = get_doc("LDAP Settings")
		set_dummy_ldap_settings(settings)

		settings.append("ldap_groups", {
			"ldap_group": "cn=Group1",
			"erpnext_role": "Test Role 1"
		})
		settings.append("ldap_groups", {
			"ldap_group": "cn=group3",
			"erpnext_role": "Test Role 3"
		})
		settings.append("ldap_groups", {
			"ldap_group": "cn=group2",
			"erpnext_role": "Test Role 2"
		})

		user = {
			"doctype": "User",
			"first_name": "bill",
			"email": "bill@test.com",
			"username": "bill",
			"send_welcome_email": 0,
			"language": "",
			"user_type": "System User",
			"roles": [{
				"role": _("Blogger")
			}]
		}

		# insert the existing user.
		the_user = get_doc(user).insert(ignore_permissions=True)

		settings.sync_roles(the_user, ['cn=group1', 'cn=group2', 'cn=group3'])

		found_roles = [d.role for d in the_user.get("roles")]

		assert ('Blogger' in found_roles and
		        'Test Role 1' in found_roles and
		        settings.default_role in found_roles and
		        'Test Role 2' in found_roles
				and 'Test Role 3' in found_roles)

	def test_authenticating_ldap_user_updates_user_if_in_database(self):
		with patch(
				"frappe.integrations.doctype.ldap_settings.ldap_settings.LDAPSettings.connect_to_ldap") as mm_conn_ldap:
			new_user_email = TEST_EMAIL
			new_user_first_name = 'Billy'
			new_user_username = 'bill'

			new_role = get_doc({
				"doctype": "Role",
				"role_name": "Test Role"})
			new_role.insert()

			settings = get_doc("LDAP Settings")
			settings.ldap_email_field = "email"
			settings.ldap_username_field = "username"
			settings.ldap_first_name_field = "first_name"
			settings.ldap_search_string = "cn={0}"
			settings.organizational_unit = "ou=test,o=lab"
			settings.ldap_server_url = "test"
			settings.base_dn = "cn=bill,ou=test,o=lab"
			settings.password = "whatever"
			settings.default_role = new_role.name
			settings.enabled = True
			settings.save()

			user = {
				"doctype": "User",
				"first_name": "JIM",
				"email": new_user_email,
				"username": "JIMMY",
				"send_welcome_email": 0,
				"language": "",
				"user_type": "System User",
				"roles": [{
					"role": _("Blogger")
				}]
			}

			# insert the existing user.
			get_doc(user).insert(ignore_permissions=True)

			server = ldap3.Server('my_fake_server')
			connection = ldap3.Connection(server,
			                              user='cn=bill,ou=test,o=lab',
			                              password='my_password',
			                              client_strategy=ldap3.MOCK_SYNC)
			connection.strategy.add_entry("cn={0},ou=test,o=lab".format(new_user_username),
			                              {"first_name": new_user_first_name,
			                               "email": new_user_email,
			                               "username": new_user_username
			                               })
			connection.bind()

			mm_conn_ldap.return_value = connection
			assert (frappe.db.exists("User", new_user_email))
			settings.authenticate(new_user_username,
			                      "whatever")
			assert (frappe.db.exists("User", new_user_email))
			new_user = get_doc("User",
			                   new_user_email)

			assert (new_user.first_name == new_user_first_name)
			assert (new_user.username == new_user_username)

			current_roles = [d.role for d in new_user.get("roles")]
			assert (settings.default_role in current_roles)

	def test_get_ldap_client_settings_no_method_set_when_ldap_not_enabled(self):
		settings = get_doc("LDAP Settings")
		set_dummy_ldap_settings(settings)
		settings.enabled = False
		settings.save()
		result = ldap_settings.LDAPSettings.get_ldap_client_settings()
		assert (result == {"enabled": False})

	def test_get_ldap_client_settings_method_set_when_ldap_is_enabled(self):
		with patch(
				"frappe.integrations.doctype.ldap_settings.ldap_settings.LDAPSettings.connect_to_ldap") as mocked_connect_to_ldap:
			settings = get_doc("LDAP Settings")
			set_dummy_ldap_settings(settings)
			settings.enabled = True
			settings.save()
			result = ldap_settings.LDAPSettings.get_ldap_client_settings()
			assert (result == {"enabled": True,
			                   "method": "frappe.integrations.doctype.ldap_settings.ldap_settings.login"})






