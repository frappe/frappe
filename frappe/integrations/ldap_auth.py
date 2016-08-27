import frappe
import ldap
from frappe.integration_broker.integration_controller import IntegrationController

class Controller(IntegrationController):
	service_name = 'LDAP Auth'
	parameters_template = [
		{
			"label": "LDAP Server Url",
			"fieldname": "ldap_server_url",
			"reqd": 1,
		},
		{
			"label": "Organizational Unit",
			"fieldname": "organizational_unit",
			"reqd": 1,
		},
		{
			"label": "Base Distinguished Name (DN)",
			"fieldname": "base_dn",
			"reqd": 1,
		},
		{
			"label": "Password for Base DN",
			"fieldname": "password",
			"reqd": 1,
		}
	]

	custom_settings = [
		{
			"label": "Sync frequency from ldap to frappe",
			"fieldname": "sync_frequency",
			"reqd": 1,
			"fieldtype": "Select",
			"options": "\nDaily\nWeekly",
		}
	]

	def enable(self, parameters, use_test_account=0):
		self.parameters = parameters
		self.validate_ldap_credentails()

	def validate_ldap_credentails(self):
		ldap_settings = self.get_settings()
		try:
			conn = ldap.initialize(ldap_settings.get('ldap_server_url'))
			conn.simple_bind_s(ldap_settings.get("base_dn"), ldap_settings.get("password"))
		except ldap.LDAPError:
			conn.unbind_s()
			frappe.throw("Incorrect UserId or Password")

	def get_settings(self):
		return frappe._dict(self.get_parameters())