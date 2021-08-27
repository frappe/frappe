# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# See license.txt
import frappe
import unittest
import functools
import ldap3
import ssl
import os

from unittest import mock
from frappe.integrations.doctype.ldap_settings.ldap_settings import LDAPSettings
from ldap3 import Server, Connection, MOCK_SYNC, OFFLINE_SLAPD_2_4, OFFLINE_AD_2012_R2


class LDAP_TestCase():
	TEST_LDAP_SERVER = None # must match the 'LDAP Settings' field option
	TEST_LDAP_SEARCH_STRING = None
	LDAP_USERNAME_FIELD = None
	DOCUMENT_GROUP_MAPPINGS = []
	LDAP_SCHEMA = None
	LDAP_LDIF_JSON = None
	TEST_VALUES_LDAP_COMPLEX_SEARCH_STRING = None

	def mock_ldap_connection(f):

		@functools.wraps(f)
		def wrapped(self, *args, **kwargs):

			with mock.patch('frappe.integrations.doctype.ldap_settings.ldap_settings.LDAPSettings.connect_to_ldap') as mock_connection:
				mock_connection.return_value = self.connection

				self.test_class = LDAPSettings(self.doc)

				# Create a clean doc
				localdoc = self.doc.copy()
				frappe.get_doc(localdoc).save()

				rv = f(self, *args, **kwargs)


			# Clean-up
			self.test_class = None

			return rv

		return wrapped

	def clean_test_users():
		try: # clean up test user 1
			frappe.get_doc("User", 'posix.user1@unit.testing').delete()
		except Exception:
			pass

		try: # clean up test user 2
			frappe.get_doc("User", 'posix.user2@unit.testing').delete()
		except Exception:
			pass


	@classmethod
	def setUpClass(self, ldapServer='OpenLDAP'):

		self.clean_test_users()
		# Save user data for restoration in tearDownClass()
		self.user_ldap_settings = frappe.get_doc('LDAP Settings')

		# Create test user1
		self.user1doc = {
			'username': 'posix.user',
			'email': 'posix.user1@unit.testing',
			'first_name': 'posix'
		}
		self.user1doc.update({
			"doctype": "User",
			"send_welcome_email": 0,
			"language": "",
			"user_type": "System User",
		})

		user = frappe.get_doc(self.user1doc)
		user.insert(ignore_permissions=True)

		# Create test user1
		self.user2doc = {
			'username': 'posix.user2',
			'email': 'posix.user2@unit.testing',
			'first_name': 'posix'
		}
		self.user2doc.update({
			"doctype": "User",
			"send_welcome_email": 0,
			"language": "",
			"user_type": "System User",
		})

		user = frappe.get_doc(self.user2doc)
		user.insert(ignore_permissions=True)


		# Setup Mock OpenLDAP Directory
		self.ldap_dc_path = 'dc=unit,dc=testing'
		self.ldap_user_path = 'ou=users,' + self.ldap_dc_path
		self.ldap_group_path = 'ou=groups,' + self.ldap_dc_path
		self.base_dn = 'cn=base_dn_user,' + self.ldap_dc_path
		self.base_password = 'my_password'
		self.ldap_server = 'ldap://my_fake_server:389'


		self.doc = {
			"doctype": "LDAP Settings",
			"enabled": True,
			"ldap_directory_server": self.TEST_LDAP_SERVER,
			"ldap_server_url": self.ldap_server,
			"base_dn": self.base_dn,
			"password": self.base_password,
			"ldap_search_path_user": self.ldap_user_path,
			"ldap_search_string": self.TEST_LDAP_SEARCH_STRING,
			"ldap_search_path_group": self.ldap_group_path,
			"ldap_user_creation_and_mapping_section": '',
			"ldap_email_field": 'mail',
			"ldap_username_field": self.LDAP_USERNAME_FIELD,
			"ldap_first_name_field": 'givenname',
			"ldap_middle_name_field": '',
			"ldap_last_name_field": 'sn',
			"ldap_phone_field": 'telephonenumber',
			"ldap_mobile_field": 'mobile',
			"ldap_security": '',
			"ssl_tls_mode": '',
			"require_trusted_certificate": 'No',
			"local_private_key_file": '',
			"local_server_certificate_file": '',
			"local_ca_certs_file": '',
			"ldap_group_objectclass": '',
			"ldap_group_member_attribute": '',
			"default_role": 'Newsletter Manager',
			"ldap_groups": self.DOCUMENT_GROUP_MAPPINGS,
			"ldap_group_field": ''}

		self.server = Server(host=self.ldap_server, port=389, get_info=self.LDAP_SCHEMA)

		self.connection = Connection(
			self.server,
			user=self.base_dn,
			password=self.base_password,
			read_only=True,
			client_strategy=MOCK_SYNC)

		self.connection.strategy.entries_from_json(os.path.abspath(os.path.dirname(__file__)) + '/' + self.LDAP_LDIF_JSON)

		self.connection.bind()


	@classmethod
	def tearDownClass(self):
		try:
			frappe.get_doc('LDAP Settings').delete()

		except Exception:
			pass

		try:
			# return doc back to user data
			self.user_ldap_settings.save()

		except Exception:
			pass

		# Clean-up test users
		self.clean_test_users()

		# Clear OpenLDAP connection
		self.connection = None

	
	@mock_ldap_connection
	def test_mandatory_fields(self):

		mandatory_fields = [
					'ldap_server_url',
					'ldap_directory_server',
					'base_dn',
					'password',
					'ldap_search_path_user',
					'ldap_search_path_group',
					'ldap_search_string',
					'ldap_email_field',
					'ldap_username_field',
					'ldap_first_name_field',
					'require_trusted_certificate',
					'default_role'
		] # fields that are required to have ldap functioning need to be mandatory

		for mandatory_field in mandatory_fields:

			localdoc = self.doc.copy()
			localdoc[mandatory_field] = ''

			try:

				frappe.get_doc(localdoc).save()

				self.fail('Document LDAP Settings field [{0}] is not mandatory'.format(mandatory_field))

			except frappe.exceptions.MandatoryError:
				pass

			except frappe.exceptions.ValidationError:
				if mandatory_field == 'ldap_search_string':
					# additional validation is done on this field, pass in this instance
					pass


		for non_mandatory_field in self.doc: # Ensure remaining fields have not been made mandatory

			if non_mandatory_field == 'doctype' or non_mandatory_field in mandatory_fields:
				continue

			localdoc = self.doc.copy()
			localdoc[non_mandatory_field] = ''
			
			try:

				frappe.get_doc(localdoc).save()

			except frappe.exceptions.MandatoryError:
				self.fail('Document LDAP Settings field [{0}] should not be mandatory'.format(non_mandatory_field))


	@mock_ldap_connection
	def test_validation_ldap_search_string(self):

		invalid_ldap_search_strings = [
					'',
					'uid={0}',
					'(uid={0}',
					'uid={0})',
					'(&(objectclass=posixgroup)(uid={0})',
					'&(objectclass=posixgroup)(uid={0}))',
					'(uid=no_placeholder)'
		] # ldap search string must be enclosed in '()' for ldap search to work for finding user and have the same number of opening and closing brackets.

		for invalid_search_string in invalid_ldap_search_strings:

			localdoc = self.doc.copy()
			localdoc['ldap_search_string'] = invalid_search_string

			try:
				frappe.get_doc(localdoc).save()

				self.fail("LDAP search string [{0}] should not validate".format(invalid_search_string))

			except frappe.exceptions.ValidationError:
				pass


	def test_connect_to_ldap(self):

		# setup a clean doc with ldap disabled so no validation occurs (this is tested seperatly)
		local_doc = self.doc.copy()
		local_doc['enabled'] = False
		self.test_class = LDAPSettings(self.doc)

		with mock.patch('ldap3.Server') as ldap3_server_method:

			with mock.patch('ldap3.Connection') as ldap3_connection_method:
				ldap3_connection_method.return_value = self.connection

				with mock.patch('ldap3.Tls') as ldap3_Tls_method:

					function_return = self.test_class.connect_to_ldap(base_dn=self.base_dn, password=self.base_password)

					args, kwargs = ldap3_connection_method.call_args

					prevent_connection_parameters = {
						# prevent these parameters for security or lack of the und user from being able to configure
						'mode': {
							'IP_V4_ONLY': 'Locks the user to IPv4 without frappe providing a way to configure',
							'IP_V6_ONLY': 'Locks the user to IPv6 without frappe providing a way to configure'
						},
						'auto_bind': {
							'NONE': 'ldap3.Connection must autobind with base_dn',
							'NO_TLS': 'ldap3.Connection must have TLS',
							'TLS_AFTER_BIND': '[Security] ldap3.Connection TLS bind must occur before bind'
						}
					}

					for connection_arg in kwargs:

						if connection_arg in prevent_connection_parameters and \
							kwargs[connection_arg] in prevent_connection_parameters[connection_arg]:

							self.fail('ldap3.Connection was called with {0}, failed reason: [{1}]'.format(
								kwargs[connection_arg],
								prevent_connection_parameters[connection_arg][kwargs[connection_arg]]))

					if local_doc['require_trusted_certificate'] == 'Yes':
						tls_validate = ssl.CERT_REQUIRED
						tls_version = ssl.PROTOCOL_TLSv1
						tls_configuration = ldap3.Tls(validate=tls_validate, version=tls_version)

						self.assertTrue(kwargs['auto_bind'] == ldap3.AUTO_BIND_TLS_BEFORE_BIND,
							'Security: [ldap3.Connection] autobind TLS before bind with value ldap3.AUTO_BIND_TLS_BEFORE_BIND')

					else:
						tls_validate = ssl.CERT_NONE
						tls_version = ssl.PROTOCOL_TLSv1
						tls_configuration = ldap3.Tls(validate=tls_validate, version=tls_version)

						self.assertTrue(kwargs['auto_bind'],
							'ldap3.Connection must autobind')


					ldap3_Tls_method.assert_called_with(validate=tls_validate, version=tls_version)

					ldap3_server_method.assert_called_with(host=self.doc['ldap_server_url'], tls=tls_configuration)

					self.assertTrue(kwargs['password'] == self.base_password,
						'ldap3.Connection password does not match provided password')

					self.assertTrue(kwargs['raise_exceptions'],
						'ldap3.Connection must raise exceptions for error handling')

					self.assertTrue(kwargs['user'] == self.base_dn,
						'ldap3.Connection user does not match provided user')

					ldap3_connection_method.assert_called_with(server=ldap3_server_method.return_value, 
						auto_bind=True,
						password=self.base_password,
						raise_exceptions=True,
						read_only=True,
						user=self.base_dn)

					self.assertTrue(type(function_return) is ldap3.core.connection.Connection,
						'The return type must be of ldap3.Connection')

					function_return = self.test_class.connect_to_ldap(base_dn=self.base_dn, password=self.base_password, read_only=False)

					args, kwargs = ldap3_connection_method.call_args

					self.assertFalse(kwargs['read_only'], 'connect_to_ldap() read_only parameter supplied as False but does not match the ldap3.Connection() read_only named parameter')




	@mock_ldap_connection
	def test_get_ldap_client_settings(self):

		result = self.test_class.get_ldap_client_settings()

		self.assertIsInstance(result, dict)

		self.assertTrue(result['enabled'] == self.doc['enabled']) # settings should match doc

		localdoc = self.doc.copy()
		localdoc['enabled'] = False
		frappe.get_doc(localdoc).save()

		result = self.test_class.get_ldap_client_settings()

		self.assertFalse(result['enabled']) # must match the edited doc


	@mock_ldap_connection
	def test_update_user_fields(self):

		test_user_data = {
			'username': 'posix.user',
			'email': 'posix.user1@unit.testing',
			'first_name': 'posix',
			'middle_name': 'another',
			'last_name': 'user',
			'phone': '08 1234 5678',
			'mobile_no': '0421 123 456'
		}

		test_user = frappe.get_doc("User", test_user_data['email'])

		self.test_class.update_user_fields(test_user, test_user_data)

		updated_user = frappe.get_doc("User", test_user_data['email'])

		self.assertTrue(updated_user.middle_name == test_user_data['middle_name'])
		self.assertTrue(updated_user.last_name == test_user_data['last_name'])
		self.assertTrue(updated_user.phone == test_user_data['phone'])
		self.assertTrue(updated_user.mobile_no == test_user_data['mobile_no'])


	@mock_ldap_connection
	def test_sync_roles(self):

		if self.TEST_LDAP_SERVER.lower() == 'openldap':
			test_user_data = {
				'posix.user1': ['Users', 'Administrators', 'default_role', 'frappe_default_all','frappe_default_guest'],
				'posix.user2': ['Users', 'Group3', 'default_role', 'frappe_default_all', 'frappe_default_guest']
			}

		elif self.TEST_LDAP_SERVER.lower() == 'active directory':
			test_user_data = {
				'posix.user1': ['Domain Users', 'Domain Administrators', 'default_role', 'frappe_default_all','frappe_default_guest'],
				'posix.user2': ['Domain Users', 'Enterprise Administrators', 'default_role', 'frappe_default_all', 'frappe_default_guest']
			}


		role_to_group_map = {
			self.doc['ldap_groups'][0]['erpnext_role']: self.doc['ldap_groups'][0]['ldap_group'],
			self.doc['ldap_groups'][1]['erpnext_role']: self.doc['ldap_groups'][1]['ldap_group'],
			self.doc['ldap_groups'][2]['erpnext_role']: self.doc['ldap_groups'][2]['ldap_group'],
			'Newsletter Manager': 'default_role',
			'All': 'frappe_default_all',
			'Guest': 'frappe_default_guest',

		}

		# re-create user1 to ensure clean
		frappe.get_doc("User", 'posix.user1@unit.testing').delete()
		user = frappe.get_doc(self.user1doc)
		user.insert(ignore_permissions=True)

		for test_user in test_user_data:

			test_user_doc = frappe.get_doc("User", test_user + '@unit.testing')
			test_user_roles = frappe.get_roles(test_user + '@unit.testing')

			self.assertTrue(len(test_user_roles) == 2,
				'User should only be a part of the All and Guest roles') # check default frappe roles

			self.test_class.sync_roles(test_user_doc, test_user_data[test_user]) # update user roles

			frappe.get_doc("User", test_user + '@unit.testing')
			updated_user_roles = frappe.get_roles(test_user + '@unit.testing')

			self.assertTrue(len(updated_user_roles) == len(test_user_data[test_user]),
				'syncing of the user roles failed. {0} != {1} for user {2}'.format(len(updated_user_roles), len(test_user_data[test_user]), test_user))

			for user_role in updated_user_roles: # match each users role mapped to ldap groups

				self.assertTrue(role_to_group_map[user_role] in test_user_data[test_user],
					'during sync_roles(), the user was given role {0} which should not have occured'.format(user_role))

	@mock_ldap_connection
	def test_create_or_update_user(self):

		test_user_data = {
			'posix.user1': ['Users', 'Administrators', 'default_role', 'frappe_default_all','frappe_default_guest'],
		}

		test_user = 'posix.user1'

		frappe.get_doc("User", test_user + '@unit.testing').delete() # remove user 1

		with self.assertRaises(frappe.exceptions.DoesNotExistError): # ensure user deleted so function can be tested
			frappe.get_doc("User", test_user + '@unit.testing')


		with mock.patch('frappe.integrations.doctype.ldap_settings.ldap_settings.LDAPSettings.update_user_fields') \
			as update_user_fields_method:

			update_user_fields_method.return_value = None


			with mock.patch('frappe.integrations.doctype.ldap_settings.ldap_settings.LDAPSettings.sync_roles') as sync_roles_method:

				sync_roles_method.return_value = None

				# New user
				self.test_class.create_or_update_user(self.user1doc, test_user_data[test_user])

				self.assertTrue(sync_roles_method.called, 'User roles need to be updated for a new user')
				self.assertFalse(update_user_fields_method.called, 
					'User roles are not required to be updated for a new user, this will occur during logon')


				# Existing user
				self.test_class.create_or_update_user(self.user1doc, test_user_data[test_user])

				self.assertTrue(sync_roles_method.called, 'User roles need to be updated for an existing user')
				self.assertTrue(update_user_fields_method.called, 'User fields need to be updated for an existing user')


	@mock_ldap_connection
	def test_get_ldap_attributes(self):

		method_return = self.test_class.get_ldap_attributes()

		self.assertTrue(type(method_return) is list)



	@mock_ldap_connection
	def test_fetch_ldap_groups(self):
	
		if self.TEST_LDAP_SERVER.lower() == 'openldap':
			test_users = {
				'posix.user': ['Users', 'Administrators'],
				'posix.user2': ['Users', 'Group3']

			}
		elif self.TEST_LDAP_SERVER.lower() == 'active directory':
			test_users = {
				'posix.user': ['Domain Users', 'Domain Administrators'],
				'posix.user2': ['Domain Users', 'Enterprise Administrators']

			}

		for test_user in test_users:

			self.connection.search(
				search_base=self.ldap_user_path,
				search_filter=self.TEST_LDAP_SEARCH_STRING.format(test_user),
				attributes=self.test_class.get_ldap_attributes())

			method_return = self.test_class.fetch_ldap_groups(self.connection.entries[0], self.connection)

			self.assertIsInstance(method_return, list)
			self.assertTrue(len(method_return) == len(test_users[test_user]))

			for returned_group in method_return:

				self.assertTrue(returned_group in test_users[test_user])



	@mock_ldap_connection
	def test_authenticate(self):
		
		with mock.patch('frappe.integrations.doctype.ldap_settings.ldap_settings.LDAPSettings.fetch_ldap_groups') as \
			fetch_ldap_groups_function:

			fetch_ldap_groups_function.return_value = None

			self.assertTrue(self.test_class.authenticate('posix.user', 'posix_user_password'))

		self.assertTrue(fetch_ldap_groups_function.called,
			'As part of authentication function fetch_ldap_groups_function needs to be called')

		invalid_users = [
			{'prefix_posix.user': 'posix_user_password'},
			{'posix.user_postfix': 'posix_user_password'},
			{'posix.user': 'posix_user_password_postfix'},
			{'posix.user': 'prefix_posix_user_password'},
			{'posix.user': ''},
			{'': 'posix_user_password'},
			{'': ''}
		] # All invalid users should return 'invalid username or password'
			
		for username, password in enumerate(invalid_users):

			with self.assertRaises(frappe.exceptions.ValidationError) as display_massage:

				self.test_class.authenticate(username, password)

			self.assertTrue(str(display_massage.exception).lower() == 'invalid username or password',
				'invalid credentials passed authentication [user: {0}, password: {1}]'.format(username, password))


	@mock_ldap_connection
	def test_complex_ldap_search_filter(self):

		ldap_search_filters = self.TEST_VALUES_LDAP_COMPLEX_SEARCH_STRING

		for search_filter in ldap_search_filters:

			self.test_class.ldap_search_string = search_filter

			if 'ACCESS:test3' in search_filter: # posix.user does not have str in ldap.description auth should fail

				with self.assertRaises(frappe.exceptions.ValidationError) as display_massage:

					self.test_class.authenticate('posix.user', 'posix_user_password')

				self.assertTrue(str(display_massage.exception).lower() == 'invalid username or password')

			else:
				self.assertTrue(self.test_class.authenticate('posix.user', 'posix_user_password'))


	def test_reset_password(self):

		self.test_class = LDAPSettings(self.doc)

		# Create a clean doc
		localdoc = self.doc.copy()

		localdoc['enabled'] = False
		frappe.get_doc(localdoc).save()

		with mock.patch('frappe.integrations.doctype.ldap_settings.ldap_settings.LDAPSettings.connect_to_ldap') as connect_to_ldap:
			connect_to_ldap.return_value = self.connection

			with self.assertRaises(frappe.exceptions.ValidationError) as validation: # Fail if username string used
				self.test_class.reset_password('posix.user', 'posix_user_password')

			self.assertTrue(str(validation.exception) == 'No LDAP User found for email: posix.user')

			try:
				self.test_class.reset_password('posix.user1@unit.testing', 'posix_user_password') # Change Password

			except Exception: # An exception from the tested class is ok, as long as the connection to LDAP was made writeable
				pass

			connect_to_ldap.assert_called_with(self.base_dn, self.base_password, read_only=False)


	@mock_ldap_connection
	def test_convert_ldap_entry_to_dict(self):

		self.connection.search(
				search_base=self.ldap_user_path,
				search_filter=self.TEST_LDAP_SEARCH_STRING.format("posix.user"),
				attributes=self.test_class.get_ldap_attributes())

		test_ldap_entry = self.connection.entries[0]

		method_return = self.test_class.convert_ldap_entry_to_dict(test_ldap_entry)

		self.assertTrue(type(method_return) is dict) # must be dict
		self.assertTrue(len(method_return) == 6) # there are 6 fields in mock_ldap for use



class Test_OpenLDAP(LDAP_TestCase, unittest.TestCase):
	TEST_LDAP_SERVER = 'OpenLDAP'
	TEST_LDAP_SEARCH_STRING = '(uid={0})'
	DOCUMENT_GROUP_MAPPINGS = [
				{
					"doctype": "LDAP Group Mapping",
					"ldap_group": "Administrators",
					"erpnext_role": "System Manager"
				},
				{
					"doctype": "LDAP Group Mapping",
					"ldap_group": "Users",
					"erpnext_role": "Blogger"
				},
				{
					"doctype": "LDAP Group Mapping",
					"ldap_group": "Group3",
					"erpnext_role": "Accounts User"
				}
	]
	LDAP_USERNAME_FIELD = 'uid'
	LDAP_SCHEMA = OFFLINE_SLAPD_2_4
	LDAP_LDIF_JSON = 'test_data_ldif_openldap.json'

	TEST_VALUES_LDAP_COMPLEX_SEARCH_STRING = [
			'(uid={0})',
			'(&(objectclass=posixaccount)(uid={0}))',
			'(&(description=*ACCESS:test1*)(uid={0}))', # OpenLDAP has no member of group, use description to filter posix.user has equivilent of AD 'memberOf'
			'(&(objectclass=posixaccount)(description=*ACCESS:test3*)(uid={0}))' # OpenLDAP has no member of group, use description to filter posix.user doesn't have. equivilent of AD 'memberOf'
	]


class Test_ActiveDirectory(LDAP_TestCase, unittest.TestCase):
	TEST_LDAP_SERVER = 'Active Directory'
	TEST_LDAP_SEARCH_STRING = '(samaccountname={0})'
	DOCUMENT_GROUP_MAPPINGS = [
				{
					"doctype": "LDAP Group Mapping",
					"ldap_group": "Domain Administrators",
					"erpnext_role": "System Manager"
				},
				{
					"doctype": "LDAP Group Mapping",
					"ldap_group": "Domain Users",
					"erpnext_role": "Blogger"
				},
				{
					"doctype": "LDAP Group Mapping",
					"ldap_group": "Enterprise Administrators",
					"erpnext_role": "Accounts User"
				}
	]
	LDAP_USERNAME_FIELD = 'samaccountname'
	LDAP_SCHEMA = OFFLINE_AD_2012_R2
	LDAP_LDIF_JSON = 'test_data_ldif_activedirectory.json'

	TEST_VALUES_LDAP_COMPLEX_SEARCH_STRING = [
			'(samaccountname={0})',
			'(&(objectclass=user)(samaccountname={0}))',
			'(&(description=*ACCESS:test1*)(samaccountname={0}))', # OpenLDAP has no member of group, use description to filter posix.user has equivilent of AD 'memberOf'
			'(&(objectclass=user)(description=*ACCESS:test3*)(samaccountname={0}))' # OpenLDAP has no member of group, use description to filter posix.user doesn't have. equivilent of AD 'memberOf'
	]

