# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, os
import httplib2

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
	from oauth2client.client import flow_from_clientsecrets
	flow = flow_from_clientsecrets(frappe.get_site_path("google_config.json"),
		scope=['https://www.googleapis.com/auth/userinfo.profile', 'https://www.googleapis.com/auth/userinfo.email'],
		redirect_uri='http://localhost:8000/api/method/frappe.templates.pages.login.login_via_google')
		
	return flow.step1_get_authorize_url()

@frappe.whitelist(allow_guest=True)
def login_via_google(code):
	from oauth2client.client import flow_from_clientsecrets
	
	
	flow = flow_from_clientsecrets(frappe.get_site_path("google_config.json"),
		scope=['https://www.googleapis.com/auth/userinfo.profile', 'https://www.googleapis.com/auth/userinfo.email'],
		redirect_uri='http://localhost:8000/api/method/frappe.templates.pages.login.login_via_google')

	credentials = flow.step2_exchange(code)

	http = httplib2.Http()
	http = credentials.authorize(http)
	
	resp, content = http.request('https://www.googleapis.com/oauth2/v2/userinfo', 'GET')
	
	print content
	
	
	