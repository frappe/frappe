import frappe
import ldap, json
from frappe.integration_broker.integration_controller import IntegrationController
from frappe import _
from frappe.utils import cstr, cint

class Controller(IntegrationController):
	service_name = 'LDAP Auth'
	parameters_template = [
		{
			"label": "LDAP Server Url",
			"fieldname": "ldap_server_url",
			"reqd": 1,
			"fieldtype": "Data"
		},
		{
			"label": "Organizational Unit",
			"fieldname": "organizational_unit",
			"reqd": 1,
			"fieldtype": "Data"
		},
		{
			"label": "Base Distinguished Name (DN)",
			"fieldname": "base_dn",
			"reqd": 1,
			"fieldtype": "Data"
		},
		{
			"label": "Password for Base DN",
			"fieldname": "password",
			"reqd": 1,
			"fieldtype": "Password"
		},
		{
			"label": "Sync frequency from ldap to frappe",
			"fieldname": "sync_frequency",
			"reqd": 1,
			"fieldtype": "Select",
			"options": "\nDaily\nWeekly",
		}
	]
	
	js = "assets/frappe/js/integrations/ldap_auth.js"
	
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
		return frappe._dict(self.parameters)

def get_ldap_settings():
	try:
		doc = frappe.get_doc("Integration Service", "LDAP Auth")
		settings = json.loads(doc.custom_settings_json)
		settings.update({
			"enabled": cint(doc.enabled),
			"method": "frappe.integrations.ldap_auth.login"
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
	conn = ldap.initialize(settings.get('ldap_server_url'))
	print settings
	try:
		# simple_bind_s is synchronous binding to server, it takes two param  DN and password
		conn.simple_bind_s(settings.get("base_dn"), settings.get("password"))
		print "here"
		#search for surnames beginning with a
		#available options for how deep a search you want.
		#LDAP_SCOPE_BASE, LDAP_SCOPE_ONELEVEL,LDAP_SCOPE_SUBTREE,
		result = conn.search_s(settings.get("organizational_unit"), ldap.SCOPE_SUBTREE,
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
	