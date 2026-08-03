from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from requests import get, post

import frappe
from frappe.utils import get_request_site_address

CALLBACK_METHOD = "/api/method/frappe.integrations.google_oauth.callback"
_SCOPES = {
	"mail": ("https://mail.google.com/"),
	"contacts": ("https://www.googleapis.com/auth/contacts"),
	"drive": ("https://www.googleapis.com/auth/drive"),
	"indexing": ("https://www.googleapis.com/auth/indexing"),
}
_SERVICES = {
	"contacts": ("people", "v1"),
	"indexing": ("indexing", "v3"),
}
_DOMAIN_CALLBACK_METHODS = {
	"mail": "frappe.email.oauth.authorize_google_access",
	"contacts": "frappe.integrations.doctype.google_contacts.google_contacts.authorize_access",
	"indexing": "frappe.website.doctype.website_settings.google_indexing.authorize_access",
}


class GoogleAuthenticationError(Exception):
	pass


GOOGLE_OAUTH_STATE_CACHE_PREFIX = "frappe_google_oauth_state"


def create_google_oauth_state(state: dict) -> str:
	"""Store this authorization attempt's state server-side and return a single-use token for it.

	The returned token is what gets sent to Google as `state`.
	"""
	token = frappe.generate_hash(length=32)
	frappe.cache.set_value(f"{GOOGLE_OAUTH_STATE_CACHE_PREFIX}:{token}", state, expires_in_sec=600)
	return token


def consume_google_oauth_state(token: str) -> dict | None:
	"""Look up and invalidate the state stored for this authorization attempt.

	Returns None if `token` doesn't reference a known, unused authorization attempt.
	"""
	if not token:
		return None
	key = f"{GOOGLE_OAUTH_STATE_CACHE_PREFIX}:{token}"
	state = frappe.cache.get_value(key)
	frappe.cache.delete_value(key)
	return state


class GoogleOAuth:
	OAUTH_URL = "https://oauth2.googleapis.com/token"

	def __init__(self, domain: str, validate: bool = True, config=None):
		self.google_settings = frappe.get_single("Google Settings")
		self.domain = domain.lower()
		self.scopes = (
			" ".join(_SCOPES[self.domain])
			if isinstance(_SCOPES[self.domain], list | tuple)
			else _SCOPES[self.domain]
		)

		if config:
			_DOMAIN_CALLBACK_METHODS[self.domain] = config["domain_callback_url"]
			_SERVICES[self.domain] = config["service_version"]

		if validate:
			self.validate_google_settings()

	def validate_google_settings(self):
		google_settings = "<a href='/desk/google-settings'>Google Settings</a>"

		if not self.google_settings.enable:
			frappe.throw(frappe._("Please enable {} before continuing.").format(google_settings))

		if not (self.google_settings.client_id and self.google_settings.client_secret):
			frappe.throw(frappe._("Please update {} before continuing.").format(google_settings))

	def authorize(self, oauth_code: str) -> dict[str, str | int]:
		"""Return a dict with access and refresh token.

		:param oauth_code: code got back from google upon successful auhtorization
		"""

		data = {
			"code": oauth_code,
			"client_id": self.google_settings.client_id,
			"client_secret": self.google_settings.get_password(
				fieldname="client_secret", raise_exception=False
			),
			"grant_type": "authorization_code",
			"scope": self.scopes,
			"redirect_uri": get_request_site_address(True) + CALLBACK_METHOD,
		}

		return handle_response(
			post(self.OAUTH_URL, data=data).json(),
			"Google Oauth Authorization Error",
			"Something went wrong during the authorization.",
		)

	def refresh_access_token(self, refresh_token: str) -> dict[str, str | int]:
		"""Refreshes google access token using refresh token"""

		data = {
			"client_id": self.google_settings.client_id,
			"client_secret": self.google_settings.get_password(
				fieldname="client_secret", raise_exception=False
			),
			"refresh_token": refresh_token,
			"grant_type": "refresh_token",
			"scope": self.scopes,
		}

		return handle_response(
			post(self.OAUTH_URL, data=data).json(),
			"Google Oauth Access Token Refresh Error",
			"Something went wrong during the access token generation.",
			raise_err=True,
		)

	def get_authentication_url(self, state: dict[str, str]) -> dict[str, str]:
		"""Return Google authentication url.

		:param state: dict of values which you need on callback (for calling methods, redirection back to the form, doc name, etc)
		"""

		# Persist the callback method in the (server-side) state so the callback can route without relying on _DOMAIN_CALLBACK_METHODS, which only lives in current worker's memory.
		state.update({"domain": self.domain, "callback_method": _DOMAIN_CALLBACK_METHODS[self.domain]})
		state_token = create_google_oauth_state(state)
		callback_url = get_request_site_address(True) + CALLBACK_METHOD

		return {
			"url": "https://accounts.google.com/o/oauth2/v2/auth?"
			+ "access_type=offline&response_type=code&prompt=consent&include_granted_scopes=true&"
			+ "client_id={}&scope={}&redirect_uri={}&state={}".format(
				self.google_settings.client_id, self.scopes, callback_url, state_token
			)
		}

	def get_google_service_object(self, access_token: str, refresh_token: str):
		"""Return Google service object."""

		credentials_dict = {
			"token": access_token,
			"refresh_token": refresh_token,
			"token_uri": self.OAUTH_URL,
			"client_id": self.google_settings.client_id,
			"client_secret": self.google_settings.get_password(
				fieldname="client_secret", raise_exception=False
			),
			"scopes": self.scopes,
		}

		return build(
			serviceName=_SERVICES[self.domain][0],
			version=_SERVICES[self.domain][1],
			credentials=Credentials(**credentials_dict),
			static_discovery=False,
		)


def handle_response(
	response: dict[str, str | int],
	error_title: str,
	error_message: str,
	raise_err: bool = False,
):
	if "error" in response:
		frappe.log_error(frappe._(error_title), frappe._(response.get("error_description", error_message)))

		if raise_err:
			frappe.throw(frappe._(error_title), GoogleAuthenticationError, frappe._(error_message))

		return {}

	return response


def is_valid_access_token(access_token: str) -> bool:
	response = get("https://oauth2.googleapis.com/tokeninfo", params={"access_token": access_token}).json()

	if "error" in response:
		return False

	return True


@frappe.whitelist(methods=["GET"])
def callback(state: str, code: str | None = None, error: str | None = None) -> None:
	"""Common callback for google integrations.
	Invokes functions using `frappe.get_attr` and also adds required (keyworded) arguments
	along with committing and redirecting us back to frappe site."""

	state = consume_google_oauth_state(state)
	if state is None:
		return frappe.respond_as_web_page(
			frappe._("Invalid Request"),
			frappe._("Your authorization attempt is invalid or has expired. Please try again."),
			http_status_code=417,
		)

	redirect = state.pop("redirect", "/desk")
	success_query_param = state.pop("success_query_param", "")
	failure_query_param = state.pop("failure_query_param", "")

	if not error:
		domain = state.pop("domain", None)
		callback_method = state.pop("callback_method", None) or _DOMAIN_CALLBACK_METHODS.get(domain)
		if callback_method:
			state.update({"code": code})
			frappe.get_attr(callback_method)(**state)

			# GET request, hence using commit to persist changes
			frappe.db.commit()  # nosemgrep
		else:
			return frappe.respond_as_web_page(
				"Invalid Google Callback",
				"The callback domain provided is not valid for Google Authentication",
				http_status_code=400,
				indicator_color="red",
				width=640,
			)

	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = f"{redirect}?{failure_query_param if error else success_query_param}"
