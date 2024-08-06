# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json

import frappe, requests
import frappe.utils
from frappe.utils.oauth import login_via_oauth2, login_via_oauth2_id_token, update_oauth_user,SignupDisabledError


@frappe.whitelist(allow_guest=True)
def login_via_google(code: str, state: str):
	login_via_oauth2("google", code, state, decoder=decoder_compat)


@frappe.whitelist(allow_guest=True)
def login_via_google_mobile(access_token):
	google_user_info_url = 'https://www.googleapis.com/oauth2/v1/userinfo'
	response = requests.get(google_user_info_url, params={'access_token': access_token})

	if response.status_code == 200:
		try:
			data = response.json()
			provider = "google"
			if update_oauth_user(user, data, provider) is False:
				pass
		except SignupDisabledError:
			return frappe.respond_as_web_page(
				"Signup is Disabled",
				"Sorry. Signup from Website is disabled.",
				success=False,
				http_status_code=403,
			)
		user_info = response.json()
		email = user_info['email']
		user = frappe.db.get_value("User", {"email": email}, "name")
		generate_login_token = True
		if user:
			if frappe.utils.cint(generate_login_token):
				login_token = frappe.generate_hash(length=32)
				frappe.cache().set_value(
					f"login_token:{login_token}", frappe.local.session.sid, expires_in_sec=120
				)
				frappe.response["login_token"] = login_token

			frappe.local.login_manager.user = user
			frappe.local.login_manager.post_login()
			frappe.db.commit()
			frappe.local.response["message"] = "Logged in successfully"
			return
		else:
			frappe.local.response["message"] = "User not found"
			return

	frappe.local.response["message"] = "Invalid token"




@frappe.whitelist(allow_guest=True)
def login_via_github(code: str, state: str):
	login_via_oauth2("github", code, state)


@frappe.whitelist(allow_guest=True)
def login_via_facebook(code: str, state: str):
	login_via_oauth2("facebook", code, state, decoder=decoder_compat)


@frappe.whitelist(allow_guest=True)
def login_via_frappe(code: str, state: str):
	login_via_oauth2("frappe", code, state, decoder=decoder_compat)


@frappe.whitelist(allow_guest=True)
def login_via_office365(code: str, state: str):
	login_via_oauth2_id_token("office_365", code, state, decoder=decoder_compat)


@frappe.whitelist(allow_guest=True)
def login_via_salesforce(code: str, state: str):
	login_via_oauth2("salesforce", code, state, decoder=decoder_compat)


@frappe.whitelist(allow_guest=True)
def login_via_fairlogin(code: str, state: str):
	login_via_oauth2("fairlogin", code, state, decoder=decoder_compat)


@frappe.whitelist(allow_guest=True)
def custom(code: str, state: str):
	"""
	Callback for processing code and state for user added providers

	process social login from /api/method/frappe.integrations.custom/<provider>
	"""
	path = frappe.request.path[1:].split("/")
	if len(path) == 4 and path[3]:
		provider = path[3]
		# Validates if provider doctype exists
		if frappe.db.exists("Social Login Key", provider):
			login_via_oauth2(provider, code, state, decoder=decoder_compat)


def decoder_compat(b):
	# https://github.com/litl/rauth/issues/145#issuecomment-31199471
	return json.loads(bytes(b).decode("utf-8"))
