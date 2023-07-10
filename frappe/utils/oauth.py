# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import base64
import json
from typing import TYPE_CHECKING, Callable

import frappe
import frappe.utils
from frappe import _
from frappe.utils.password import get_decrypted_password

if TYPE_CHECKING:
	from frappe.core.doctype.user.user import User


class SignupDisabledError(frappe.PermissionError):
	...


def get_oauth2_providers() -> dict[str, dict]:
	out = {}
	providers = frappe.get_all("Social Login Key", fields=["*"])
	for provider in providers:
		authorize_url, access_token_url = provider.authorize_url, provider.access_token_url
		if provider.custom_base_url:
			authorize_url = provider.base_url + provider.authorize_url
			access_token_url = provider.base_url + provider.access_token_url
		out[provider.name] = {
			"flow_params": {
				"name": provider.name,
				"authorize_url": authorize_url,
				"access_token_url": access_token_url,
				"base_url": provider.base_url,
			},
			"redirect_uri": provider.redirect_url,
			"api_endpoint": provider.api_endpoint,
		}
		if provider.auth_url_data:
			out[provider.name]["auth_url_data"] = json.loads(provider.auth_url_data)

		if provider.api_endpoint_args:
			out[provider.name]["api_endpoint_args"] = json.loads(provider.api_endpoint_args)

	return out


def get_oauth_keys(provider: str) -> dict[str, str]:
	"""get client_id and client_secret from database or conf"""

	if keys := frappe.conf.get(f"{provider}_login"):
		return {"client_id": keys["client_id"], "client_secret": keys["client_secret"]}

	return {
		"client_id": frappe.db.get_value("Social Login Key", provider, "client_id"),
		"client_secret": get_decrypted_password("Social Login Key", provider, "client_secret"),
	}


def get_oauth2_authorize_url(provider: str, redirect_to: str) -> str:
	flow = get_oauth2_flow(provider)

	state = {
		"site": frappe.utils.get_url(),
		"token": frappe.generate_hash(),
		"redirect_to": redirect_to,
	}

	# relative to absolute url
	data = {
		"redirect_uri": get_redirect_uri(provider),
		"state": base64.b64encode(bytes(json.dumps(state).encode("utf-8"))),
	}

	oauth2_providers = get_oauth2_providers()

	# additional data if any
	data.update(oauth2_providers[provider].get("auth_url_data", {}))

	return flow.get_authorize_url(**data)


def get_oauth2_flow(provider: str):
	from rauth import OAuth2Service

	# get client_id and client_secret
	params = get_oauth_keys(provider)

	oauth2_providers = get_oauth2_providers()

	# additional params for getting the flow
	params.update(oauth2_providers[provider]["flow_params"])

	# and we have setup the communication lines
	return OAuth2Service(**params)


def get_redirect_uri(provider: str) -> str:
	keys = frappe.conf.get(f"{provider}_login")

	if keys and keys.get("redirect_uri"):
		# this should be a fully qualified redirect uri
		return keys["redirect_uri"]

	oauth2_providers = get_oauth2_providers()
	redirect_uri = oauth2_providers[provider]["redirect_uri"]

	# this uses the site's url + the relative redirect uri
	return frappe.utils.get_url(redirect_uri)


def login_via_oauth2(provider: str, code: str, state: str, decoder: Callable | None = None):
	info = get_info_via_oauth(provider, code, decoder)
	login_oauth_user(info, provider=provider, state=state)


def login_via_oauth2_id_token(
	provider: str, code: str, state: str, decoder: Callable | None = None
):
	info = get_info_via_oauth(provider, code, decoder, id_token=True)
	login_oauth_user(info, provider=provider, state=state)


def get_info_via_oauth(
	provider: str, code: str, decoder: Callable | None = None, id_token: bool = False
):

	import jwt

	flow = get_oauth2_flow(provider)
	oauth2_providers = get_oauth2_providers()

	args = {
		"data": {
			"code": code,
			"redirect_uri": get_redirect_uri(provider),
			"grant_type": "authorization_code",
		}
	}

	if decoder:
		args["decoder"] = decoder

	session = flow.get_auth_session(**args)

	if id_token:
		parsed_access = json.loads(session.access_token_response.text)
		token = parsed_access["id_token"]
		info = jwt.decode(token, flow.client_secret, options={"verify_signature": False})

	else:
		api_endpoint = oauth2_providers[provider].get("api_endpoint")
		api_endpoint_args = oauth2_providers[provider].get("api_endpoint_args")
		info = session.get(api_endpoint, params=api_endpoint_args).json()

		if provider == "github" and not info.get("email"):
			emails = session.get("/user/emails", params=api_endpoint_args).json()
			email_dict = list(filter(lambda x: x.get("primary"), emails))[0]
			info["email"] = email_dict.get("email")

	if not (info.get("email_verified") or info.get("email")):
		frappe.throw(_("Email not verified with {0}").format(provider.title()))

	return info


def login_oauth_user(
	data: dict | str,
	provider: str | None = None,
	state: dict | str | None = None,
	email_id: str | None = None,
	key: str | None = None,
	generate_login_token: bool = False,
):
	# json.loads data and state
	if isinstance(data, str):
		data = json.loads(data)

	if isinstance(state, str):
		state = base64.b64decode(state)
		state = json.loads(state.decode("utf-8"))

	if not (state and state["token"]):
		frappe.respond_as_web_page(_("Invalid Request"), _("Token is missing"), http_status_code=417)
		return

	user = get_email(data)

	if not user:
		frappe.respond_as_web_page(
			_("Invalid Request"), _("Please ensure that your profile has an email address")
		)
		return

	try:
		if update_oauth_user(user, data, provider) is False:
			return

	except SignupDisabledError:
		return frappe.respond_as_web_page(
			"Signup is Disabled",
			"Sorry. Signup from Website is disabled.",
			success=False,
			http_status_code=403,
		)

	frappe.local.login_manager.user = user
	frappe.local.login_manager.post_login()

	# because of a GET request!
	frappe.db.commit()

	if frappe.utils.cint(generate_login_token):
		login_token = frappe.generate_hash(length=32)
		frappe.cache().set_value(
			f"login_token:{login_token}", frappe.local.session.sid, expires_in_sec=120
		)

		frappe.response["login_token"] = login_token

	else:
		redirect_to = state.get("redirect_to")
		redirect_post_login(
			desk_user=frappe.local.response.get("message") == "Logged In",
			redirect_to=redirect_to,
			provider=provider,
		)


def get_user_record(user: str, data: dict) -> "User":
	try:
		return frappe.get_doc("User", user)
	except frappe.DoesNotExistError:
		if frappe.get_website_settings("disable_signup"):
			raise SignupDisabledError

	user: "User" = frappe.new_doc("User")

	if gender := data.get("gender", "").title():
		frappe.get_doc({"doctype": "Gender", "gender": gender}).insert(
			ignore_permissions=True, ignore_if_duplicate=True
		)

	user.update(
		{
			"doctype": "User",
			"first_name": get_first_name(data),
			"last_name": get_last_name(data),
			"email": get_email(data),
			"gender": gender,
			"enabled": 1,
			"new_password": frappe.generate_hash(),
			"location": data.get("location"),
			"user_type": "Website User",
			"user_image": data.get("picture") or data.get("avatar_url"),
		}
	)

	return user


def update_oauth_user(user: str, data: dict, provider: str):
	if isinstance(data.get("location"), dict):
		data["location"] = data["location"].get("name")

	user: "User" = get_user_record(user, data)
	update_user_record = user.is_new()

	if not user.enabled:
		frappe.respond_as_web_page(_("Not Allowed"), _("User {0} is disabled").format(user.email))
		return False

	if not user.get_social_login_userid(provider):
		update_user_record = True
		match provider:
			case "facebook":
				user.set_social_login_userid(provider, userid=data["id"], username=data.get("username"))
				user.update({"user_image": f"https://graph.facebook.com/{data['id']}/picture"})
			case "google":
				user.set_social_login_userid(provider, userid=data["id"])
			case "github":
				user.set_social_login_userid(provider, userid=data["id"], username=data.get("login"))
			case "frappe" | "office_365":
				user.set_social_login_userid(provider, userid=data["sub"])
			case "salesforce":
				user.set_social_login_userid(provider, userid="/".join(data["sub"].split("/")[-2:]))
			case _:
				user_id_property = (
					frappe.db.get_value("Social Login Key", provider, "user_id_property") or "sub"
				)
				user.set_social_login_userid(provider, userid=data[user_id_property])

	if update_user_record:
		user.flags.ignore_permissions = True
		user.flags.no_welcome_mail = True

		if default_role := frappe.db.get_single_value("Portal Settings", "default_role"):
			user.add_roles(default_role)

		user.save()


def get_first_name(data: dict) -> str:
	return data.get("first_name") or data.get("given_name") or data.get("name")


def get_last_name(data: dict) -> str:
	return data.get("last_name") or data.get("family_name")


def get_email(data: dict) -> str:
	return data.get("email") or data.get("upn") or data.get("unique_name")


def redirect_post_login(
	desk_user: bool, redirect_to: str | None = None, provider: str | None = None
):
	frappe.local.response["type"] = "redirect"

	if not redirect_to:
		desk_uri = "/app/workspace" if provider == "facebook" else "/app"
		redirect_to = frappe.utils.get_url(desk_uri if desk_user else "/me")

	frappe.local.response["location"] = redirect_to
