# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.twofactor import (should_run_2fa, authenticate_for_2factor, confirm_otp_token)

class LDAPSettings(Document):
	def validate(self):
		if not self.enabled:
			return

		if not self.flags.ignore_mandatory:
			if self.ldap_search_string and self.ldap_search_string.endswith("={0}"):
				self.connect_to_ldap(base_dn=self.base_dn, password=self.get_password(raise_exception=False))
			else:
				frappe.throw(_("LDAP Search String needs to end with a placeholder, eg sAMAccountName={0}"))

	def connect_to_ldap(self, base_dn, password):
		try:
			import ldap3
			import ssl

			if self.require_trusted_certificate == 'Yes':
				tls_configuration = ldap3.Tls(validate=ssl.CERT_REQUIRED, version=ssl.PROTOCOL_TLSv1)
			else:
				tls_configuration = ldap3.Tls(validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLSv1)

			if self.local_private_key_file:
				tls_configuration.private_key_file = self.local_private_key_file
			if self.local_server_certificate_file:
				tls_configuration.certificate_file = self.local_server_certificate_file
			if self.local_ca_certs_file:
				tls_configuration.ca_certs_file = self.local_ca_certs_file

			server = ldap3.Server(host=self.ldap_server_url, tls=tls_configuration)
			bind_type = ldap3.AUTO_BIND_TLS_BEFORE_BIND if self.ssl_tls_mode == "StartTLS" else True

			conn = ldap3.Connection(
				server=server,
				user=base_dn,
				password=password,
				auto_bind=bind_type,
				read_only=True,
				raise_exceptions=True)

			return conn

		except ImportError:
			msg = _("Please Install the ldap3 library via pip to use ldap functionality.")
			frappe.throw(msg, title=_("LDAP Not Installed"))
		except ldap3.core.exceptions.LDAPInvalidCredentialsResult:
			frappe.throw(_("Invalid username or password"))
		except Exception as ex:
			frappe.throw(_(str(ex)))

	@staticmethod
	def get_ldap_client_settings():
		# return the settings to be used on the client side.
		result = {
			"enabled": False
		}
		ldap = frappe.get_doc("LDAP Settings")
		if ldap.enabled:
			result["enabled"] = True
			result["method"] = "frappe.integrations.doctype.ldap_settings.ldap_settings.login"
		return result

	@classmethod
	def update_user_fields(cls, user, user_data):

		updatable_data = {key: value for key, value in user_data.items() if key != 'email'}

		for key, value in updatable_data.items():
			setattr(user, key, value)
		user.save(ignore_permissions=True)

	def sync_roles(self, user, additional_groups=None):

		current_roles = set([d.role for d in user.get("roles")])

		needed_roles = set()
		needed_roles.add(self.default_role)

		lower_groups = [g.lower() for g in additional_groups or []]

		all_mapped_roles = {r.erpnext_role for r in self.ldap_groups}
		matched_roles = {r.erpnext_role for r in self.ldap_groups if r.ldap_group.lower() in lower_groups}
		unmatched_roles = all_mapped_roles.difference(matched_roles)
		needed_roles.update(matched_roles)
		roles_to_remove = current_roles.intersection(unmatched_roles)

		if not needed_roles.issubset(current_roles):
			missing_roles = needed_roles.difference(current_roles)
			user.add_roles(*missing_roles)

		user.remove_roles(*roles_to_remove)

	def create_or_update_user(self, user_data, groups=None):
		user = None
		if frappe.db.exists("User", user_data['email']):
			user = frappe.get_doc("User", user_data['email'])
			LDAPSettings.update_user_fields(user=user, user_data=user_data)
		else:
			doc = user_data
			doc.update({
				"doctype": "User",
				"send_welcome_email": 0,
				"language": "",
				"user_type": "System User",
				# "roles": [{
				# 	"role": self.default_role
				# }]
			})
			user = frappe.get_doc(doc)
			user.insert(ignore_permissions=True)
		# always add default role.
		user.add_roles(self.default_role)
		if self.ldap_group_field:
			self.sync_roles(user, groups)
		return user

	def get_ldap_attributes(self):
		ldap_attributes = [self.ldap_email_field, self.ldap_username_field, self.ldap_first_name_field]

		if self.ldap_group_field:
			ldap_attributes.append(self.ldap_group_field)

		if self.ldap_middle_name_field:
			ldap_attributes.append(self.ldap_middle_name_field)

		if self.ldap_last_name_field:
			ldap_attributes.append(self.ldap_last_name_field)

		if self.ldap_phone_field:
			ldap_attributes.append(self.ldap_phone_field)

		if self.ldap_mobile_field:
			ldap_attributes.append(self.ldap_mobile_field)

		return ldap_attributes

	def authenticate(self, username, password):

		if not self.enabled:
			frappe.throw(_("LDAP is not enabled."))

		user_filter = self.ldap_search_string.format(username)
		ldap_attributes = self.get_ldap_attributes()

		conn = self.connect_to_ldap(self.base_dn, self.get_password(raise_exception=False))

		conn.search(
			search_base=self.organizational_unit,
			search_filter="({0})".format(user_filter),
			attributes=ldap_attributes)

		if len(conn.entries) == 1 and conn.entries[0]:
			user = conn.entries[0]
			# only try and connect as the user, once we have their fqdn entry.
			self.connect_to_ldap(base_dn=user.entry_dn, password=password)

			groups = None
			if self.ldap_group_field:
				groups = getattr(user, self.ldap_group_field).values
			return self.create_or_update_user(self.convert_ldap_entry_to_dict(user), groups=groups)
		else:
			frappe.throw(_("Invalid username or password"))

	def convert_ldap_entry_to_dict(self, user_entry):

		# support multiple email values
		email = user_entry[self.ldap_email_field]

		data = {
			'username': user_entry[self.ldap_username_field].value,
			'email': str(email.value[0] if isinstance(email.value, list) else email.value),
			'first_name': user_entry[self.ldap_first_name_field].value
		}

		# optional fields

		if self.ldap_middle_name_field:
			data['middle_name'] = user_entry[self.ldap_middle_name_field].value

		if self.ldap_last_name_field:
			data['last_name'] = user_entry[self.ldap_last_name_field].value

		if self.ldap_phone_field:
			data['phone'] = user_entry[self.ldap_phone_field].value

		if self.ldap_mobile_field:
			data['mobile_no'] = user_entry[self.ldap_mobile_field].value

		return data


@frappe.whitelist(allow_guest=True)
def login():
	# LDAP LOGIN LOGIC
	args = frappe.form_dict
	ldap = frappe.get_doc("LDAP Settings")

	user = ldap.authenticate(frappe.as_unicode(args.usr), frappe.as_unicode(args.pwd))

	frappe.local.login_manager.user = user.name
	if should_run_2fa(user.name):
		authenticate_for_2factor(user.name)
		if not confirm_otp_token(frappe.local.login_manager):
			return False
	frappe.local.login_manager.post_login()

	# because of a GET request!
	frappe.db.commit()
