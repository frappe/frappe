from __future__ import unicode_literals
import frappe

def execute():
	frappe.reload_doc("integrations", "doctype", "social_login_keys")
	frappe_server_url = frappe.get_value("Social Login Keys", None, "frappe_server_url")
	existing_providers = [
		{
			"access_token_url": "https://accounts.google.com/o/oauth2/token", 
			"api_endpoint": "oauth2/v2/userinfo", 
			"api_endpoint_args": "", 
			"auth_url_data": "{\"scope\":\"https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/userinfo.email\",\"response_type\": \"code\"}", 
			"authorize_url": "https://accounts.google.com/o/oauth2/auth", 
			"base_url": "https://www.googleapis.com", 
			"client_id": frappe.get_value("Social Login Keys", None, "google_client_id"), 
			"client_secret": frappe.get_value("Social Login Keys", None, "google_client_secret"), 
			"decoder": "JSON", 
			"doctype": "Social Login Key", 
			"enable_social_login": 1, 
			"icon": "fa fa-google", 
			"is_standard": 1, 
			"name": "google", 
			"openid_connect": "API Endpoint", 
			"provider_name": "Google", 
			"redirect_url": "/api/method/frappe.www.login.login_via_google"
		}, 
		{
			"access_token_url": "https://graph.facebook.com/oauth/access_token", 
			"api_endpoint": "/v2.5/me", 
			"api_endpoint_args": "{\"fields\": \"first_name,last_name,email,gender,location,verified,picture\"}", 
			"auth_url_data": "{\"display\": \"page\",\"response_type\": \"code\",\"scope\": \"email,public_profile\"}", 
			"authorize_url": "https://www.facebook.com/dialog/oauth", 
			"base_url": "https://graph.facebook.com", 
			"client_id": frappe.get_value("Social Login Keys", None, "facebook_client_id"), 
			"client_secret": frappe.get_value("Social Login Keys", None, "facebook_client_secret"), 
			"decoder": "JSON", 
			"doctype": "Social Login Key", 
			"enable_social_login": 1, 
			"icon": "fa fa-facebook", 
			"is_standard": 1, 
			"openid_connect": "API Endpoint", 
			"provider_name": "Facebook", 
			"redirect_url": "/api/method/frappe.www.login.login_via_facebook"
		}, 
		{
			"access_token_url": "https://github.com/login/oauth/access_token", 
			"api_endpoint": "user", 
			"api_endpoint_args": None, 
			"auth_url_data": None, 
			"authorize_url": "https://github.com/login/oauth/authorize", 
			"base_url": "https://api.github.com/", 
			"client_id": frappe.get_value("Social Login Keys", None, "github_client_id"), 
			"client_secret": frappe.get_value("Social Login Keys", None, "github_client_secret"), 
			"decoder": "", 
			"doctype": "Social Login Key", 
			"enable_social_login": 1, 
			"icon": "fa fa-github", 
			"is_standard": 1, 
			"openid_connect": "API Endpoint", 
			"provider_name": "Github", 
			"redirect_url": "/api/method/frappe.www.login.login_via_github"
		},
		{
			"access_token_url": frappe_server_url+"/api/method/frappe.integrations.oauth2.get_token", 
			"api_endpoint": frappe_server_url+"/api/method/frappe.integrations.oauth2.openid_profile",
			"api_endpoint_args": None,
			"auth_url_data": "{\"response_type\":\"code\",\"scope\":\"openid\"}",
			"authorize_url": "/api/method/frappe.integrations.oauth2.authorize",
			"base_url": frappe_server_url,
			"client_id": frappe.get_value("Social Login Keys", None, "frappe_client_id"),
			"client_secret": frappe.get_value("Social Login Keys", None, "frappe_client_secret"),
			"decoder": "",
			"doctype": "Social Login Key",
			"enable_social_login": 1,
			"icon": "fa fa-github",
			"is_standard": 1,
			"openid_connect": "API Endpoint",
			"provider_name": "Frappe",
			"redirect_url": "/api/method/frappe.www.login.login_via_frappe"
		}
	]
	delete_user_fields()

	for key in existing_providers:
		key = frappe._dict(key)
		key_doc = frappe.new_doc(key.doctype)
		key_doc.access_token_url = key.access_token_url
		key_doc.api_endpoint = key.api_endpoint
		key_doc.api_endpoint_args = key.api_endpoint_args
		key_doc.auth_url_data = key.auth_url_data
		key_doc.authorize_url = key.authorize_url
		key_doc.base_url = key.base_url
		key_doc.client_id = key.client_id
		key_doc.client_secret = key.client_secret
		key_doc.decoder = key.decoder
		key_doc.enable_social_login = key.enable_social_login
		key_doc.icon = key.icon
		key_doc.is_standard = key.is_standard
		key_doc.openid_connect = key.openid_connect
		key_doc.provider_name = key.provider_name
		key_doc.redirect_url = key.redirect_url
		key_doc.save()
		frappe.db.commit()

def delete_user_fields():
	fieldnames = [
		"facebook_username", "facebook_userid",
		"github_username", "github_userid",
		"google_username", "google_userid",
		"frappe_userid"
	]
	for f in fieldnames:
		d = frappe.get_all("DocField", {"parent":"User","fieldname":f})
		if d:
			frappe.delete_doc("DocField", d[0].get("name"))
