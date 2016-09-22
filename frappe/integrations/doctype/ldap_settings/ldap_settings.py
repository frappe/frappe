# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import ldap
from frappe import _
from frappe.utils import cstr, cint
from frappe.integration_broker.doctype.integration_service.integration_service import IntegrationService

service_details=""" LDAP based authentication:
"""

class LDAPSettings(IntegrationService):
	def on_update(self):
		pass
	
	def validate(self):
		if not self.flags.ignore_mandatory:
			self.validate_ldap_credentails()
	
	def enable(self):
		if not self.flags.ignore_mandatory:
			self.validate_ldap_credentails()

	def validate_ldap_credentails(self):
		try:
			conn = ldap.initialize(self.ldap_server_url)
			conn.simple_bind_s(self.base_dn, self.get_password(raise_exception=False))
		except ldap.LDAPError:
			conn.unbind_s()
			frappe.throw("Incorrect UserId or Password")

@frappe.whitelist()
def get_service_details():
	return service_details

def get_ldap_settings():
	try:
		settings = frappe.get_doc("LDAP Settings")

		settings.update({
			"enabled": cint(frappe.db.get_value("Integration Service", "LDAP", "enabled")),
			"method": "frappe.integrations.doctype.ldap_settings.ldap_settings.login"
		})
		return settings
	except Exception:
		# this will return blank settings
		return frappe._dict()
	
@frappe.whitelist(allow_guest=True)
def login():
	#### LDAP LOGIN LOGIC #####
	args = frappe.form_dict
	user = authenticate_ldap_user(args.usr, args.pwd)

	frappe.local.login_manager.user = user.name
	frappe.local.login_manager.post_login()

	# because of a GET request!
	frappe.db.commit()

def authenticate_ldap_user(user=None, password=None):
	dn = None
	params = {}
	settings = get_ldap_settings()
	conn = ldap.initialize(settings.ldap_server_url)

	try:
		# simple_bind_s is synchronous binding to server, it takes two param  DN and password
		conn.simple_bind_s(settings.base_dn, settings.get_password(raise_exception=False))

		#search for surnames beginning with a
		#available options for how deep a search you want.
		#LDAP_SCOPE_BASE, LDAP_SCOPE_ONELEVEL,LDAP_SCOPE_SUBTREE,
		result = conn.search_s(settings.organizational_unit, ldap.SCOPE_SUBTREE,
			"uid=*{0}".format(user))
		
		print result
		
		for dn, r in result:
			dn = cstr(dn)
			params["email"] = cstr(r['mail'][0])
			params["username"] = cstr(r['uid'][0])
			params["first_name"] = cstr(r['cn'][0])
			
		if dn:
			conn.simple_bind_s(dn, password)
			return create_user(params)
		else:
			frappe.throw(_("Not a valid LDAP user"))

	except ldap.LDAPError:
		conn.unbind_s()
		frappe.throw(_("Incorrect UserId or Password"))

def create_user(params):
	if frappe.db.exists("User", params["email"]):
		return frappe.get_doc("User", params["email"])
	
	else:
		params.update({
			"doctype": "User",
			"send_welcome_email": 0,
			"language": "",
			"user_type": "System User",
			"user_roles": [{
				"role": _("Blogger")
			}]
		})

		user = frappe.get_doc(params).insert(ignore_permissions=True)
		frappe.db.commit()
		
		return user