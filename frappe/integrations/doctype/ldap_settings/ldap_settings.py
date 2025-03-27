# Copyright (c) 2022, Frappe Technologies and contributors
# License: MIT. See LICENSE

import ssl
from typing import TYPE_CHECKING

import ldap3
from ldap3 import AUTO_BIND_TLS_BEFORE_BIND, HASHED_SALTED_SHA, MODIFY_REPLACE
from ldap3.abstract.entry import Entry
from ldap3.core.exceptions import (
	LDAPAttributeError,
	LDAPInvalidCredentialsResult,
	LDAPInvalidFilterError,
	LDAPNoSuchObjectResult,
)
from ldap3.utils.conv import escape_filter_chars
from ldap3.utils.hashed import hashed

import frappe
from frappe import _, safe_encode
from frappe.model.document import Document
from frappe.twofactor import authenticate_for_2factor, confirm_otp_token, should_run_2fa

if TYPE_CHECKING:
	from frappe.core.doctype.user.user import User


class LDAPSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.integrations.doctype.ldap_group_mapping.ldap_group_mapping import LDAPGroupMapping
		from frappe.types import DF

		base_dn: DF.Data
		default_role: DF.Link | None
		default_user_type: DF.Link
		do_not_create_new_user: DF.Check
		enabled: DF.Check
		ldap_custom_group_search: DF.Data | None
		ldap_directory_server: DF.Literal["", "Active Directory", "OpenLDAP", "Custom"]
		ldap_email_field: DF.Data
		ldap_first_name_field: DF.Data
		ldap_group_field: DF.Data | None
		ldap_group_member_attribute: DF.Data | None
		ldap_group_objectclass: DF.Data | None
		ldap_groups: DF.Table[LDAPGroupMapping]
		ldap_last_name_field: DF.Data | None
		ldap_middle_name_field: DF.Data | None
		ldap_mobile_field: DF.Data | None
		ldap_phone_field: DF.Data | None
		ldap_search_path_group: DF.Data
		ldap_search_path_user: DF.Data
		ldap_search_string: DF.Data
		ldap_server_url: DF.Data
		ldap_username_field: DF.Data
		local_ca_certs_file: DF.Data | None
		local_private_key_file: DF.Data | None
		local_server_certificate_file: DF.Data | None
		password: DF.Password
		require_trusted_certificate: DF.Literal["No", "Yes"]
		ssl_tls_mode: DF.Literal["Off", "StartTLS"]
	# end: auto-generated types

	def validate(self):
		self.default_user_type = self.default_user_type or "Website User"

		if not self.enabled:
			return

		if not self.flags.ignore_mandatory:
			if (
				self.ldap_search_string.count("(") == self.ldap_search_string.count(")")
				and self.ldap_search_string.startswith("(")
				and self.ldap_search_string.endswith(")")
				and self.ldap_search_string
				and "{0}" in self.ldap_search_string
			):
				conn = self.connect_to_ldap(
					base_dn=self.base_dn, password=self.get_password(raise_exception=False)
				)

				try:
					if conn.result["type"] == "bindResponse" and self.base_dn:
						conn.search(
							search_base=self.ldap_search_path_user,
							search_filter="(objectClass=*)",
							attributes=self.get_ldap_attributes(),
						)

						conn.search(
							search_base=self.ldap_search_path_group,
							search_filter="(objectClass=*)",
							attributes=["cn"],
						)

				except LDAPAttributeError as ex:
					frappe.throw(
						_("LDAP settings incorrect. validation response was: {0}").format(ex),
						title=_("Misconfigured"),
					)

				except LDAPNoSuchObjectResult:
					frappe.throw(
						_("Ensure the user and group search paths are correct."), title=_("Misconfigured")
					)

				if self.ldap_directory_server.lower() == "custom":
					if not self.ldap_group_member_attribute or not self.ldap_group_objectclass:
						frappe.throw(
							_(
								"Custom LDAP Directoy Selected, please ensure 'LDAP Group Member attribute' and 'Group Object Class' are entered"
							),
							title=_("Misconfigured"),
						)

				if self.ldap_custom_group_search and "{0}" not in self.ldap_custom_group_search:
					frappe.throw(
						_(
							"Custom Group Search if filled needs to contain the user placeholder {0}, eg uid={0},ou=users,dc=example,dc=com"
						),
						title=_("Misconfigured"),
					)

			else:
				frappe.throw(
					_(
						"LDAP Search String must be enclosed in '()' and needs to contian the user placeholder {0}, eg sAMAccountName={0}"
					)
				)

	def connect_to_ldap(self, base_dn, password, read_only=True) -> ldap3.Connection:
		try:
			if self.require_trusted_certificate == "Yes":
				tls_configuration = ldap3.Tls(validate=ssl.CERT_REQUIRED, version=ssl.PROTOCOL_TLS_CLIENT)
			else:
				tls_configuration = ldap3.Tls(validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLS_CLIENT)

			if self.local_private_key_file:
				tls_configuration.private_key_file = self.local_private_key_file
			if self.local_server_certificate_file:
				tls_configuration.certificate_file = self.local_server_certificate_file
			if self.local_ca_certs_file:
				tls_configuration.ca_certs_file = self.local_ca_certs_file

			server = ldap3.Server(host=self.ldap_server_url, tls=tls_configuration)
			bind_type = AUTO_BIND_TLS_BEFORE_BIND if self.ssl_tls_mode == "StartTLS" else True

			return ldap3.Connection(
				server=server,
				user=base_dn,
				password=password,
				auto_bind=bind_type,
				read_only=read_only,
				raise_exceptions=True,
			)

		except ImportError:
			msg = _("Please Install the ldap3 library via pip to use ldap functionality.")
			frappe.throw(msg, title=_("LDAP Not Installed"))
		except LDAPInvalidCredentialsResult:
			frappe.throw(_("Invalid username or password"))
		except Exception as ex:
			frappe.throw(_(str(ex)))

	@staticmethod
	def get_ldap_client_settings() -> dict:
		# return the settings to be used on the client side.
		result = {"enabled": False}
		ldap = frappe.get_cached_doc("LDAP Settings")
		if ldap.enabled:
			result["enabled"] = True
			result["method"] = "frappe.integrations.doctype.ldap_settings.ldap_settings.login"
		return result

	@classmethod
	def update_user_fields(cls, user: "User", user_data: dict):
		updatable_data = {key: value for key, value in user_data.items() if key != "email"}

		for key, value in updatable_data.items():
			setattr(user, key, value)
		user.save(ignore_permissions=True)

	def sync_roles(self, user: "User", additional_groups: list | None = None):
		current_roles = {d.role for d in user.get("roles")}
		if self.default_user_type == "System User":
			needed_roles = {self.default_role}
		else:
			needed_roles = set()
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

	def create_or_update_user(self, user_data: dict, groups: list | None = None):
		user: User = None
		role: str = None

		if frappe.db.exists("User", user_data["email"]):
			user = frappe.get_doc("User", user_data["email"])
			LDAPSettings.update_user_fields(user=user, user_data=user_data)
		elif not self.do_not_create_new_user:
			doc = user_data | {
				"doctype": "User",
				"send_welcome_email": 0,
				"language": "",
				"user_type": self.default_user_type,
			}
			user = frappe.get_doc(doc)
			user.insert(ignore_permissions=True)
		else:
			frappe.throw(
				_(
					"User with email: {0} does not exist in the system. Please ask 'System Administrator' to create the user for you."
				).format(user_data["email"])
			)

		if self.default_user_type == "System User":
			role = self.default_role
		else:
			role = frappe.db.get_value("User Type", user.user_type, "role")

		if role:
			user.add_roles(role)

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

	def fetch_ldap_groups(self, user: Entry, conn: ldap3.Connection) -> list:
		if not isinstance(user, Entry):
			raise TypeError("Invalid type, attribute 'user' must be of type 'ldap3.abstract.entry.Entry'")

		if not isinstance(conn, ldap3.Connection):
			raise TypeError("Invalid type, attribute 'conn' must be of type 'ldap3.Connection'")

		fetch_ldap_groups = None
		ldap_object_class = None
		ldap_group_members_attribute = None

		if self.ldap_directory_server.lower() == "active directory":
			ldap_object_class = "Group"
			ldap_group_members_attribute = "member"
			user_search_str = escape_filter_chars(user.entry_dn)

		elif self.ldap_directory_server.lower() == "openldap":
			ldap_object_class = "posixgroup"
			ldap_group_members_attribute = "memberuid"
			user_search_str = getattr(user, self.ldap_username_field).value

		elif self.ldap_directory_server.lower() == "custom":
			ldap_object_class = self.ldap_group_objectclass
			ldap_group_members_attribute = self.ldap_group_member_attribute
			ldap_custom_group_search = self.ldap_custom_group_search or "{0}"
			user_search_str = ldap_custom_group_search.format(getattr(user, self.ldap_username_field).value)

		else:
			# NOTE: depreciate this else path
			# this path will be hit for everyone with preconfigured ldap settings. this must be taken into account so as not to break ldap for those users.

			if self.ldap_group_field:
				fetch_ldap_groups = getattr(user, self.ldap_group_field).values

		if ldap_object_class is not None:
			conn.search(
				search_base=self.ldap_search_path_group,
				search_filter=f"(&(objectClass={ldap_object_class})({ldap_group_members_attribute}={user_search_str}))",
				attributes=["cn"],
			)  # Build search query

		if len(conn.entries) >= 1:
			fetch_ldap_groups = [group["cn"].value for group in conn.entries]
		return fetch_ldap_groups

	def authenticate(self, username: str, password: str):
		if not self.enabled:
			frappe.throw(_("LDAP is not enabled."))

		user_filter = self.ldap_search_string.format(username)
		ldap_attributes = self.get_ldap_attributes()
		conn = self.connect_to_ldap(self.base_dn, self.get_password(raise_exception=False))

		try:
			conn.search(
				search_base=self.ldap_search_path_user,
				search_filter=f"{user_filter}",
				attributes=ldap_attributes,
			)

			if len(conn.entries) == 1 and conn.entries[0]:
				user = conn.entries[0]
				groups = self.fetch_ldap_groups(user, conn)

				# only try and connect as the user, once we have their fqdn entry.
				if user.entry_dn and password and conn.rebind(user=user.entry_dn, password=password):
					return self.create_or_update_user(self.convert_ldap_entry_to_dict(user), groups=groups)

			raise LDAPInvalidCredentialsResult  # even though nothing foundor failed authentication raise invalid credentials

		except LDAPInvalidFilterError:
			frappe.throw(_("Please use a valid LDAP search filter"), title=_("Misconfigured"))

		except LDAPInvalidCredentialsResult:
			frappe.throw(_("Invalid username or password"))

	def reset_password(self, user, password, logout_sessions=False):
		search_filter = f"({self.ldap_email_field}={user})"

		conn = self.connect_to_ldap(self.base_dn, self.get_password(raise_exception=False), read_only=False)

		if conn.search(
			search_base=self.ldap_search_path_user,
			search_filter=search_filter,
			attributes=self.get_ldap_attributes(),
		):
			if conn.entries and conn.entries[0]:
				entry_dn = conn.entries[0].entry_dn
				hashed_password = hashed(HASHED_SALTED_SHA, safe_encode(password))
				changes = {"userPassword": [(MODIFY_REPLACE, [hashed_password])]}
				if conn.modify(entry_dn, changes=changes):
					if logout_sessions:
						from frappe.sessions import clear_sessions

						clear_sessions(user=user, force=True)
					frappe.msgprint(_("Password changed successfully."))
				else:
					frappe.throw(_("Failed to change password."))
			else:
				frappe.throw(_("No Entry for the User {0} found within LDAP!").format(user))
		else:
			frappe.throw(_("No LDAP User found for email: {0}").format(user))

	def convert_ldap_entry_to_dict(self, user_entry: Entry):
		# support multiple email values
		email = user_entry[self.ldap_email_field].value

		if isinstance(email, list):
			# check if any of the email in the list already exist
			for e in email:
				if frappe.db.exists("User", e):
					email = e
					break
			else:
				# if none of the email exist, use the first email
				email = email[0]

		data = {
			"username": user_entry[self.ldap_username_field].value,
			"email": email,
			"first_name": user_entry[self.ldap_first_name_field].value,
		}

		# optional fields
		if self.ldap_middle_name_field:
			data["middle_name"] = user_entry[self.ldap_middle_name_field].value

		if self.ldap_last_name_field:
			data["last_name"] = user_entry[self.ldap_last_name_field].value

		if self.ldap_phone_field:
			data["phone"] = user_entry[self.ldap_phone_field].value

		if self.ldap_mobile_field:
			data["mobile_no"] = user_entry[self.ldap_mobile_field].value

		return data


@frappe.whitelist(allow_guest=True)
def login():
	# LDAP LOGIN LOGIC
	args = frappe.form_dict
	ldap: LDAPSettings = frappe.get_doc("LDAP Settings")

	user = ldap.authenticate(frappe.as_unicode(args.usr), frappe.as_unicode(args.pwd))

	frappe.local.login_manager.user = user.name
	if should_run_2fa(user.name):
		authenticate_for_2factor(user.name)
		if not confirm_otp_token(frappe.local.login_manager):
			return False

	frappe.form_dict.pop("pwd", None)
	frappe.local.login_manager.post_login()

	# because of a GET request!
	frappe.db.commit()


@frappe.whitelist()
def reset_password(user, password, logout):
	ldap: LDAPSettings = frappe.get_doc("LDAP Settings")
	if not ldap.enabled:
		frappe.throw(_("LDAP is not enabled."))
	ldap.reset_password(user, password, logout_sessions=int(logout))
