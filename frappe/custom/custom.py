# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json

import frappe, requests
import frappe.utils
from frappe.utils.oauth import update_oauth_user, SignupDisabledError, get_email

@frappe.whitelist(allow_guest=True)
def login_via_google_mobile(access_token):
	google_user_info_url = 'https://www.googleapis.com/oauth2/v1/userinfo'
	response = requests.get(google_user_info_url, params={'access_token': access_token})

	if response.status_code == 200:
		try:
			data = response.json()
			user = get_email(data)
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

