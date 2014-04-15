# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import json
import frappe.utils
from frappe import _

no_cache = True

def get_context(context):
	# get settings from site config
	context["title"] = "Login"

	for provider in ("google", "github", "facebook"):
		if get_oauth_keys(provider):
			context["{provider}_login".format(provider=provider)] = get_oauth2_authorize_url(provider)
			context["social_login"] = True

	return context

oauth2_providers = {
	"google": {
		"flow_params": {
			"name": "google",
			"authorize_url": "https://accounts.google.com/o/oauth2/auth",
			"access_token_url": "https://accounts.google.com/o/oauth2/token",
			"base_url": "https://www.googleapis.com",
		},

		"redirect_uri": "/api/method/frappe.templates.pages.login.login_via_google",

		"auth_url_data": {
			"scope": "https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/userinfo.email",
			"response_type": "code"
		},

		# relative to base_url
		"api_endpoint": "oauth2/v2/userinfo"
	},

	"github": {
		"flow_params": {
			"name": "github",
			"authorize_url": "https://github.com/login/oauth/authorize",
			"access_token_url": "https://github.com/login/oauth/access_token",
			"base_url": "https://api.github.com/"
		},

		"redirect_uri": "/api/method/frappe.templates.pages.login.login_via_github",

		# relative to base_url
		"api_endpoint": "user"
	},

	"facebook": {
		"flow_params": {
			"name": "facebook",
			"authorize_url": "https://www.facebook.com/dialog/oauth",
			"access_token_url": "https://graph.facebook.com/oauth/access_token",
			"base_url": "https://graph.facebook.com"
		},

		"redirect_uri": "/api/method/frappe.templates.pages.login.login_via_facebook",

		"auth_url_data": {
			"display": "page",
			"response_type": "code",
			"scope": "email,user_birthday"
		},

		# relative to base_url
		"api_endpoint": "me"
	}
}

def get_oauth_keys(provider):
	"""get client_id and client_secret from database or conf"""

	# try conf
	keys = frappe.conf.get("{provider}_login".format(provider=provider))

	if not keys:
		# try database
		social = frappe.get_doc("Social Login Keys", "Social Login Keys")
		keys = {}
		for fieldname in ("client_id", "client_secret"):
			value = social.get("{provider}_{fieldname}".format(provider=provider, fieldname=fieldname))
			if not value:
				keys = {}
				break
			keys[fieldname] = value

	return keys

def get_oauth2_authorize_url(provider):
	flow = get_oauth2_flow(provider)

	# relative to absolute url
	data = { "redirect_uri": get_redirect_uri(provider) }

	# additional data if any
	data.update(oauth2_providers[provider].get("auth_url_data", {}))

	return flow.get_authorize_url(**data)

def get_oauth2_flow(provider):
	from rauth import OAuth2Service

	# get client_id and client_secret
	params = get_oauth_keys(provider)

	# additional params for getting the flow
	params.update(oauth2_providers[provider]["flow_params"])

	# and we have setup the communication lines
	return OAuth2Service(**params)

def get_redirect_uri(provider):
	redirect_uri = oauth2_providers[provider]["redirect_uri"]
	return frappe.utils.get_url(redirect_uri)

@frappe.whitelist(allow_guest=True)
def login_via_google(code):
	login_via_oauth2("google", code, decoder=json.loads)

@frappe.whitelist(allow_guest=True)
def login_via_github(code):
	login_via_oauth2("github", code)

@frappe.whitelist(allow_guest=True)
def login_via_facebook(code):
	login_via_oauth2("facebook", code)

def login_via_oauth2(provider, code, decoder=None):
	flow = get_oauth2_flow(provider)

	args = {
		"data": {
			"code": code,
			"redirect_uri": get_redirect_uri(provider),
			"grant_type": "authorization_code"
		}
	}
	if decoder:
		args["decoder"] = decoder

	session = flow.get_auth_session(**args)

	api_endpoint = oauth2_providers[provider].get("api_endpoint")
	info = session.get(api_endpoint).json()

	if "verified_email" in info and not info.get("verified_email"):
		frappe.throw(_("Email not verified with {1}").format(provider.title()))

	login_oauth_user(info, provider=provider)

def login_oauth_user(data, provider=None):
	user = data["email"]

	if not frappe.db.exists("User", user):
		create_oauth_user(data, provider)

	frappe.local.login_manager.user = user
	frappe.local.login_manager.post_login()

	# redirect!
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = "/app" if frappe.local.response.get('message') == 'Logged In' else "/"

	# because of a GET request!
	frappe.db.commit()

def create_oauth_user(data, provider):
	if data.get("birthday"):
		from frappe.utils.dateutils import parse_date
		data["birthday"] = parse_date(data["birthday"])

	if isinstance(data.get("location"), dict):
		data["location"] = data.get("location").get("name")

	user = frappe.get_doc({
		"doctype":"User",
		"first_name": data.get("first_name") or data.get("given_name") or data.get("name"),
		"last_name": data.get("last_name") or data.get("family_name"),
		"email": data["email"],
		"gender": data.get("gender"),
		"enabled": 1,
		"new_password": frappe.generate_hash(data["email"]),
		"location": data.get("location"),
		"birth_date":  data.get("birthday"),
		"user_type": "Website User",
		"user_image": data.get("picture") or data.get("avatar_url")
	})

	if provider=="facebook":
		user.update({
			"fb_username": data["username"],
			"fb_userid": data["id"],
			"user_image": "https://graph.facebook.com/{username}/picture".format(username=data["username"])
		})
	elif provider=="google":
		user.google_userid = data["id"]

	elif provider=="github":
		user.github_userid = data["id"]
		user.github_username = data["login"]

	user.ignore_permissions = True
	user.no_welcome_mail = True
	user.insert()
