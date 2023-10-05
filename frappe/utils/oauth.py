# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import base64
import json
from collections.abc import Callable
from typing import TYPE_CHECKING

import frappe
import frappe.utils
from frappe import _
from frappe.utils.password import get_decrypted_password

if TYPE_CHECKING:
	from frappe.core.doctype.user.user import User


class SignupDisabledError(frappe.PermissionError):
	...


def get_oauth2_providers() -> dict[str, dict]:
	"""
	Get a dictionary of OAuth2 providers.

	This function retrieves a dictionary of OAuth2 providers from the 'Social Login
	Key' table in the database.
	Each provider is represented as a dictionary with the following keys:
	- 'flow_params': Contains information about the provider's name, authorize URL,
	access token URL, and base URL.
	- 'redirect_uri': Contains the provider's redirect URL.
	- 'api_endpoint': Contains the provider's API endpoint.
	The function queries the 'Social Login Key' table to fetch the necessary data
	and constructs the output dictionary accordingly.

	Returns:
		dict[str, dict]: A dictionary of OAuth2 providers.
	"""
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
	"""
	Get the redirect URI for the specified OAuth2 provider.

	Args:
		provider (str): The OAuth2 provider name.

	Returns:
		str: The redirect URI.
	"""
	keys = frappe.conf.get(f"{provider}_login")

	if keys and keys.get("redirect_uri"):
		# this should be a fully qualified redirect uri
		return keys["redirect_uri"]

	oauth2_providers = get_oauth2_providers()
	redirect_uri = oauth2_providers[provider]["redirect_uri"]

	# this uses the site's url + the relative redirect uri
	return frappe.utils.get_url(redirect_uri)


def login_via_oauth2(provider: str, code: str, state: str, decoder: Callable | None = None):
	"""
	Log in the user via OAuth2 using the specified provider, code, state, and decoder.

	Args:
		provider (str): The OAuth2 provider name.
		code (str): The authorization code.
		state (str): The state parameter.
		decoder (Callable | None, optional): The decoder to use for decoding
			the response. Defaults to None.
	"""
	info = get_info_via_oauth(provider, code, decoder)
	login_oauth_user(info, provider=provider, state=state)


def login_via_oauth2_id_token(
	provider: str, code: str, state: str, decoder: Callable | None = None
):
	"""
	Log in the user via OAuth2 using the specified provider, code, state, and decoder.
	This function additionally retrieves information using the id_token flag.

	Args:
		provider (str): The OAuth2 provider name.
		code (str): The authorization code.
		state (str): The state parameter.
		decoder (Callable | None, optional): The decoder to use for decoding
			the response. Defaults to None.
	"""
	info = get_info_via_oauth(provider, code, decoder, id_token=True)
	login_oauth_user(info, provider=provider, state=state)


def get_info_via_oauth(
	provider: str, code: str, decoder: Callable | None = None, id_token: bool = False
):
	"""
	Retrieve information from an OAuth provider.

	The function takes in the provider name, authorization code, decoder function
	(optional),
	and a boolean flag indicating whether to include the ID token in the response.
	It performs the necessary API requests to obtain the desired information from
	the provider and returns it.

	Args:
		provider (str): The name of the OAuth provider.
		code (str): The authorization code.
		decoder (Callable | None, optional): The decoder function for decoding
			the response. Defaults to None.
		id_token (bool, optional): Flag indicating whether to include the ID
			token in the response. Defaults to False.

	Returns:
		dict: The retrieved information from the OAuth provider.
	"""

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
	*,
	provider: str | None = None,
	state: dict | str,
	generate_login_token: bool = False,
):
	"""
	Function to handle OAuth login process for a user.

	This function takes in a 'data' parameter, which can be a dictionary or a string,
	and a 'state' parameter, which can be a dictionary or a string.
	The 'provider' parameter is an optional string and the 'generate_login_token' parameter
	is a boolean with a default value of False.

	Args:
		data (dict | str): The data containing user information in the form of
			a dictionary or a JSON string.
		provider (str | None, optional): The OAuth provider. Defaults to None.
		state (dict | str): The state containing additional information in the
			form of a dictionary or a JSON string.
		generate_login_token (bool, optional): Whether to generate a login token.
		Defaults to False.
	"""
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
		frappe.cache.set_value(
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
	"""
	Get the user record for the given user name and data.

	This function retrieves a user record using the 'frappe.get_doc' function and
	returns it. If the record does not exist, it checks if user signup is
	disabled using the 'frappe.get_website_settings' function and raises a
	'SignupDisabledError' if signup is disabled. Then, it creates a new user
	record using the 'frappe.new_doc' function and sets various field values
	based on the provided data. Finally, it returns the created user object.

	Args:
		user (str): The name of the user.
		data (dict): The data for creating the user record.

	Returns:
		User: The user record.
	"""
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
	"""
	Update an OAuth user record.

	This function is used to update an OAuth user record with the provided data. It
	takes three parameters: 'user' (a string representing the user
	identifier), 'data' (a dictionary containing the updated data for the
	user), and 'provider' (a string representing the OAuth provider).

	The function performs the following operations:
	- If the 'location' key in the 'data' dictionary is a dictionary, it is
	replaced with the value of the 'name' key.
	- The user record is retrieved using the 'get_user_record' function.
	- If the user is disabled, a web page response is sent and False is returned.
	- If the social login ID for the specified provider is not found, the user
	record is updated based on the provider value.
	- If the 'update_user_record' flag is set, the user record is saved with the updated
	  information.
	"""
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
	"""
	Return the first name from the given data dictionary.

	This function retrieves the value associated with the key 'first_name',
	'given_name', or 'name' from the data dictionary.
	The value is returned as a string.

	Args:
		data (dict): A dictionary containing the data.

	Returns:
		str: The first name.
	"""
	return data.get("first_name") or data.get("given_name") or data.get("name")


def get_last_name(data: dict) -> str:
	"""
	Return the last name from the given data dictionary.

	This function retrieves the value associated with the key 'last_name' or
	'family_name' from the data dictionary.
	The value is returned as a string.

	Args:
		data (dict): A dictionary containing the data.

	Returns:
		str: The last name.
	"""
	return data.get("last_name") or data.get("family_name")


def get_email(data: dict) -> str:
	"""
	Return the email from the given data dictionary.

	This function retrieves the value associated with the key 'email', 'upn', or
	'unique_name' from the data dictionary.
	The value is returned as a string.

	Args:
		data (dict): A dictionary containing the data.

	Returns:
		str: The email.
	"""
	return data.get("email") or data.get("upn") or data.get("unique_name")


def redirect_post_login(
	desk_user: bool, redirect_to: str | None = None, provider: str | None = None
):
	"""
	Redirect the user to a specific location after login.

	This function sets the 'type' key in the local 'response' dictionary to 'redirect'.
	If 'redirect_to' is not provided, it sets 'redirect_to' based on the 'provider'
	value and determines the 'location' key in the local 'response' dictionary.

	Args:
		desk_user (bool): A boolean indicating whether the user is a desk user.
		redirect_to (str, optional): The URL to redirect to after login. Defaults to None.
		provider (str, optional): The provider. Defaults to None.
	"""
	frappe.local.response["type"] = "redirect"

	if not redirect_to:
		desk_uri = "/app/workspace" if provider == "facebook" else "/app"
		redirect_to = frappe.utils.get_url(desk_uri if desk_user else "/me")

	frappe.local.response["location"] = redirect_to
