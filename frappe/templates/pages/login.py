# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, os
import httplib2
import json
from werkzeug.utils import redirect

no_cache = True

def get_context(context):
	# get settings from site config
	context["title"] = "Login"
	if frappe.conf.get("fb_app_id"):
		context.update({ "fb_app_id": frappe.conf.fb_app_id })
		
	if os.path.exists(frappe.get_site_path("google_config.json")):
		context.update({ "google_sign_in": get_google_auth_url() })
		
	return context

def get_google_auth_url():
	flow = get_google_auth_flow()
	return flow.step1_get_authorize_url()

def get_google_auth_flow():
	from oauth2client.client import flow_from_clientsecrets
	google_config_path = frappe.get_site_path("google_config.json")
	google_config = frappe.get_file_json(google_config_path)
	
	flow = flow_from_clientsecrets(google_config_path,
		scope=['https://www.googleapis.com/auth/userinfo.profile', 'https://www.googleapis.com/auth/userinfo.email'],
		redirect_uri=google_config.get("web").get("redirect_uris")[0])

	return flow
	
@frappe.whitelist(allow_guest=True)
def login_via_google(code):
	flow = get_google_auth_flow()
	credentials = flow.step2_exchange(code)

	http = httplib2.Http()
	http = credentials.authorize(http)
	
	resp, content = http.request('https://www.googleapis.com/oauth2/v2/userinfo', 'GET')
	info = json.loads(content)
	
	if not info.get("verified_email"):
		frappe.throw("You need to verify your email with Google before you can proceed.")
	
	frappe.local._response = redirect("/")
	
	login_oauth_user(info, oauth_provider="google")
	
	# because of a GET request!
	frappe.db.commit()
	
@frappe.whitelist(allow_guest=True)
def login_via_facebook(data):
	data = json.loads(data)
	
	if not (data.get("id") and data.get("fb_access_token")):
		raise frappe.ValidationError

	if not get_fb_userid(data.get("fb_access_token")):
		# garbage
		raise frappe.ValidationError
		
	login_oauth_user(data, oauth_provider="facebook")
	
def login_oauth_user(data, oauth_provider=None):
	user = data["email"]
	
	if not frappe.db.exists("Profile", user):
		create_oauth_user(data, oauth_provider)
	
	frappe.local.login_manager.user = user
	frappe.local.login_manager.post_login()
	
def create_oauth_user(data, oauth_provider):
	if data.get("birthday"):
		b = data.get("birthday").split("/")
		data["birthday"] = b[2] + "-" + b[0] + "-" + b[1]
	
	profile = frappe.bean({
		"doctype":"Profile",
		"first_name": data.get("first_name") or data.get("given_name"),
		"last_name": data.get("last_name") or data.get("family_name"),
		"email": data["email"],
		"gender": data.get("gender"),
		"enabled": 1,
		"new_password": frappe.generate_hash(data["email"]),
		"location": data.get("location", {}).get("name"),
		"birth_date":  data.get("birthday"),
		"user_type": "Website User",
		"user_image": data.get("picture")
	})
	
	if oauth_provider=="facebook":
		profile.doc.fields.update({
			"fb_username": data["username"],
			"fb_userid": data["id"]
		})
	elif oauth_provider=="google":
		profile.doc.google_userid = data["id"]
	
	profile.ignore_permissions = True
	profile.get_controller().no_welcome_mail = True
	profile.insert()

def get_fb_userid(fb_access_token):
	import requests
	response = requests.get("https://graph.facebook.com/me?access_token=" + fb_access_token)
	if response.status_code==200:
		print response.json()
		return response.json().get("id")
	else:
		return frappe.AuthenticationError