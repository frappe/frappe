# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import frappe.utils
import json
from frappe import _
from six import string_types

class SignupDisabledError(frappe.PermissionError): pass

def get_oauth2_providers():
	out = {
		"google": {
			"flow_params": {
				"name": "google",
				"authorize_url": "https://accounts.google.com/o/oauth2/auth",
				"access_token_url": "https://accounts.google.com/o/oauth2/token",
				"base_url": "https://www.googleapis.com",
			},

			"redirect_uri": "/api/method/frappe.www.login.login_via_google",

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

			"redirect_uri": "/api/method/frappe.www.login.login_via_github",

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

			"redirect_uri": "/api/method/frappe.www.login.login_via_facebook",

			"auth_url_data": {
				"display": "page",
				"response_type": "code",
				"scope": "email,public_profile"
			},

			# relative to base_url
			"api_endpoint": "/v2.5/me",
			"api_endpoint_args": {
				"fields": "first_name,last_name,email,gender,location,verified,picture"
			},
		}
	}

	frappe_server_url = frappe.db.get_value("Social Login Keys", None, "frappe_server_url")
	if frappe_server_url:
		out['frappe'] = {
			"flow_params": {
				"name": "frappe",
				"authorize_url": frappe_server_url + "/api/method/frappe.integrations.oauth2.authorize",
				"access_token_url": frappe_server_url + "/api/method/frappe.integrations.oauth2.get_token",
				"base_url": frappe_server_url
			},

			"redirect_uri": "/api/method/frappe.www.login.login_via_frappe",

			"auth_url_data": {
				"response_type": "code",
				"scope": "openid"
			},

			# relative to base_url
			"api_endpoint": "/api/method/frappe.integrations.oauth2.openid_profile"
		}

	return out

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

	else:
		return {
			"client_id": keys["client_id"],
			"client_secret": keys["client_secret"]
		}

def get_oauth2_authorize_url(provider):
	flow = get_oauth2_flow(provider)

	state = { "site": frappe.utils.get_url(), "token": frappe.generate_hash() }
	frappe.cache().set_value("{0}:{1}".format(provider, state["token"]), True, expires_in_sec=120)

	# relative to absolute url
	data = {
		"redirect_uri": get_redirect_uri(provider),
		"state": json.dumps(state)
	}

	oauth2_providers = get_oauth2_providers()

	# additional data if any
	data.update(oauth2_providers[provider].get("auth_url_data", {}))

	return flow.get_authorize_url(**data)

def get_oauth2_flow(provider):
	from rauth import OAuth2Service

	# get client_id and client_secret
	params = get_oauth_keys(provider)

	oauth2_providers = get_oauth2_providers()

	# additional params for getting the flow
	params.update(oauth2_providers[provider]["flow_params"])

	# and we have setup the communication lines
	return OAuth2Service(**params)

def get_redirect_uri(provider):
	keys = frappe.conf.get("{provider}_login".format(provider=provider))

	if keys and keys.get("redirect_uri"):
		# this should be a fully qualified redirect uri
		return keys["redirect_uri"]

	else:
		oauth2_providers = get_oauth2_providers()

		redirect_uri = oauth2_providers[provider]["redirect_uri"]

		# this uses the site's url + the relative redirect uri
		return frappe.utils.get_url(redirect_uri)

def login_via_oauth2(provider, code, state, decoder=None):
	info = get_info_via_oauth(provider, code, decoder)
	login_oauth_user(info, provider=provider, state=state)

def get_info_via_oauth(provider, code, decoder=None):
	flow = get_oauth2_flow(provider)
	oauth2_providers = get_oauth2_providers()

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
	api_endpoint_args = oauth2_providers[provider].get("api_endpoint_args")
	info = session.get(api_endpoint, params=api_endpoint_args).json()

	if (("verified_email" in info and not info.get("verified_email"))
		or ("verified" in info and not info.get("verified"))):
		frappe.throw(_("Email not verified with {1}").format(provider.title()))

	return info

def login_oauth_user(data=None, provider=None, state=None, email_id=None, key=None, generate_login_token=False):
	# NOTE: This could lead to security issue as the signed in user can type any email address in complete_signup
	# if email_id and key:
	# 	data = json.loads(frappe.db.get_temp(key))
	#	# What if data is missing because of an invalid key
	# 	data["email"] = email_id
	#
	# elif not (data.get("email") and get_first_name(data)) and not frappe.db.exists("User", data.get("email")):
	# 	# ask for user email
	# 	key = frappe.db.set_temp(json.dumps(data))
	# 	frappe.db.commit()
	# 	frappe.local.response["type"] = "redirect"
	# 	frappe.local.response["location"] = "/complete_signup?key=" + key
	# 	return

	# json.loads data and state
	if isinstance(data, string_types):
		data = json.loads(data)

	if isinstance(state, string_types):
		state = json.loads(state)

	if not (state and state["token"]):
		frappe.respond_as_web_page(_("Invalid Request"), _("Token is missing"), http_status_code=417)
		return

	token = frappe.cache().get_value("{0}:{1}".format(provider, state["token"]), expires=True)
	if not token:
		frappe.respond_as_web_page(_("Invalid Request"), _("Invalid Token"), http_status_code=417)
		return

	user = data["email"]

	if not user:
		frappe.respond_as_web_page(_("Invalid Request"), _("Please ensure that your profile has an email address"))
		return

	try:
		if update_oauth_user(user, data, provider) is False:
			return

	except SignupDisabledError:
		return frappe.respond_as_web_page("Signup is Disabled", "Sorry. Signup from Website is disabled.",
			success=False, http_status_code=403)

	frappe.local.login_manager.user = user
	frappe.local.login_manager.post_login()

	# because of a GET request!
	frappe.db.commit()

	if frappe.utils.cint(generate_login_token):
		login_token = frappe.generate_hash(length=32)
		frappe.cache().set_value("login_token:{0}".format(login_token), frappe.local.session.sid, expires_in_sec=120)

		frappe.response["login_token"] = login_token

	else:
		redirect_post_login(desk_user=frappe.local.response.get('message') == 'Logged In')

def update_oauth_user(user, data, provider):
	if isinstance(data.get("location"), dict):
		data["location"] = data.get("location").get("name")

	save = False

	if not frappe.db.exists("User", user):

		# is signup disabled?
		if frappe.utils.cint(frappe.db.get_single_value("Website Settings", "disable_signup")):
			raise SignupDisabledError

		save = True
		user = frappe.new_doc("User")
		user.update({
			"doctype":"User",
			"first_name": get_first_name(data),
			"last_name": get_last_name(data),
			"email": data["email"],
			"gender": (data.get("gender") or "").title(),
			"enabled": 1,
			"new_password": frappe.generate_hash(data["email"]),
			"location": data.get("location"),
			"user_type": "Website User",
			"user_image": data.get("picture") or data.get("avatar_url")
		})

	else:
		user = frappe.get_doc("User", user)
		if not user.enabled:
			frappe.respond_as_web_page(_('Not Allowed'), _('User {0} is disabled').format(user.email))
			return False

	if provider=="facebook" and not user.get("fb_userid"):
		save = True
		user.update({
			"fb_username": data.get("username"),
			"fb_userid": data["id"],
			"user_image": "https://graph.facebook.com/{id}/picture".format(id=data["id"])
		})

	elif provider=="google" and not user.get("google_userid"):
		save = True
		user.google_userid = data["id"]

	elif provider=="github" and not user.get("github_userid"):
		save = True
		user.github_userid = data["id"]
		user.github_username = data["login"]

	elif provider=="frappe" and not user.get("frappe_userid"):
		save = True
		user.frappe_userid = data["sub"]

	if save:
		user.flags.ignore_permissions = True
		user.flags.no_welcome_mail = True
		user.save()

def get_first_name(data):
	return data.get("first_name") or data.get("given_name") or data.get("name")

def get_last_name(data):
	return data.get("last_name") or data.get("family_name")

def redirect_post_login(desk_user):
	# redirect!
	frappe.local.response["type"] = "redirect"

	# the #desktop is added to prevent a facebook redirect bug
	frappe.local.response["location"] = "/desk#desktop" if desk_user else "/"
