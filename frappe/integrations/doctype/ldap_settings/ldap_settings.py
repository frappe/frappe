# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document


class LDAPSettings(Document):
	def validate(self):
		if not self.enabled:
			return

		if not self.flags.ignore_mandatory:
			if self.ldap_search_string and self.ldap_search_string.endswith("={0}"):
				connect_to_ldap(server_url=self.ldap_server_url,
					base_dn=self.base_dn,
					password=self.get_password(raise_exception=False),
					ssl_tls_mode=self.ssl_tls_mode,
					trusted_cert=self.require_trusted_certificate,
					private_key_file=self.local_private_key_file,
					server_cert_file=self.local_server_certificate_file,
					ca_certs_file=self.local_ca_certs_file
				)
			else:
				frappe.throw(_("LDAP Search String needs to end with a placeholder, eg sAMAccountName={0}"))


def get_ldap_client_settings():
	#return the settings to be used on the client side.
	result = {
		"enabled": False
	}
	settings = frappe.get_doc("LDAP Settings")

	if settings and settings.enabled:
		result["enabled"] = True
		result["method"] = "frappe.integrations.doctype.ldap_settings.ldap_settings.login"
	return result


def connect_to_ldap(server_url,
                    base_dn,
                    password,
                    ssl_tls_mode,
                    trusted_cert,
                    private_key_file,
                    server_cert_file,
                    ca_certs_file):
	try:
		import ldap3
		import ssl

		if trusted_cert == 'Yes':
			tls_configuration = ldap3.Tls(validate=ssl.CERT_REQUIRED,
			                              version=ssl.PROTOCOL_TLSv1)
		else:
			tls_configuration = ldap3.Tls(validate=ssl.CERT_NONE,
			                              version=ssl.PROTOCOL_TLSv1)

		if private_key_file:
			tls_configuration.private_key_file = private_key_file
		if server_cert_file:
			tls_configuration.certificate_file = server_cert_file
		if ca_certs_file:
			tls_configuration.ca_certs_file = ca_certs_file

		server = ldap3.Server(host=server_url,
		                      tls=tls_configuration)
		bind_type = ldap3.AUTO_BIND_TLS_BEFORE_BIND if ssl_tls_mode == "StartTLS" else True

		conn = ldap3.Connection(server=server,
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
		frappe.throw(_("Invalid Credentials"))
	except Exception as ex:
		frappe.throw(_(str(ex)))


@frappe.whitelist(allow_guest=True)
def login():
	# LDAP LOGIN LOGIC
	args = frappe.form_dict
	user = authenticate_ldap_user(frappe.as_unicode(args.usr), frappe.as_unicode(args.pwd))

	frappe.local.login_manager.user = user.name
	frappe.local.login_manager.post_login()

	# because of a GET request!
	frappe.db.commit()


def authenticate_ldap_user(user=None,
                           password=None):

	params = {}
	settings = frappe.get_doc("LDAP Settings")
	if settings and settings.enabled:
		conn = connect_to_ldap(server_url=settings.ldap_server_url,
		                       base_dn=settings.base_dn,
		                       password=settings.get_password(raise_exception=False),
		                       ssl_tls_mode=settings.ssl_tls_mode,
		                       trusted_cert=settings.require_trusted_certificate,
		                       private_key_file=settings.local_private_key_file,
		                       server_cert_file=settings.local_server_certificate_file,
		                       ca_certs_file=settings.local_ca_certs_file)

		user_filter = settings.ldap_search_string.format(user)
		conn.search(search_base=settings.organizational_unit,
		            search_filter="({0})".format(user_filter),
		            attributes=[settings.ldap_email_field,
		                        settings.ldap_username_field,
		                        settings.ldap_first_name_field])

		if len(conn.entries) > 0 and conn.entries[0]:
			user = conn.entries[0]
			params["email"] = str(user[settings.ldap_email_field])
			params["username"] = str(user[settings.ldap_username_field])
			params["first_name"] = str(user[settings.ldap_first_name_field])
			connect_to_ldap(server_url=settings.ldap_server_url,
			                base_dn=user.entry_dn,
			                password=frappe.as_unicode(password),
			                ssl_tls_mode=settings.ssl_tls_mode,
			                trusted_cert=settings.require_trusted_certificate,
			                private_key_file=settings.local_private_key_file,
			                server_cert_file=settings.local_server_certificate_file,
			                ca_certs_file=settings.local_ca_certs_file
			                )
			return create_user(params)
		else:
			frappe.throw(_("Not a valid LDAP user"))
	else:
		frappe.throw(_("LDAP is not enabled."))


def create_user(params):
	if frappe.db.exists("User", params["email"]):
		user = frappe.get_doc("User", params["email"])
		user.first_name = params["first_name"]
		user.username = params["username"]
		user.save(ignore_permissions=True)
		return user

	else:
		params.update({
			"doctype": "User",
			"send_welcome_email": 0,
			"language": "",
			"user_type": "System User",
			"roles": [{
				"role": _("Customer")
			}]
		})

		user = frappe.get_doc(params).insert(ignore_permissions=True)

		return user
