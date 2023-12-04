import base64
import datetime
import hashlib
import re
from http import cookies
from urllib.parse import unquote, urljoin, urlparse

import jwt
import pytz
from oauthlib.openid import RequestValidator

import frappe
from frappe.auth import LoginManager
from frappe.utils.data import get_system_timezone, now_datetime


class OAuthWebRequestValidator(RequestValidator):

	# Pre- and post-authorization.
	def validate_client_id(self, client_id, request, *args, **kwargs):
		# Simple validity check, does client exist? Not banned?
		cli_id = frappe.db.get_value("OAuth Client", {"name": client_id})
		if cli_id:
			request.client = frappe.get_doc("OAuth Client", client_id).as_dict()
			return True
		else:
			return False

	def validate_redirect_uri(self, client_id, redirect_uri, request, *args, **kwargs):
		# Is the client allowed to use the supplied redirect_uri? i.e. has
		# the client previously registered this EXACT redirect uri.

		redirect_uris = frappe.db.get_value("OAuth Client", client_id, "redirect_uris").split(
			get_url_delimiter()
		)

		if redirect_uri in redirect_uris:
			return True
		else:
			return False

	def get_default_redirect_uri(self, client_id, request, *args, **kwargs):
		# The redirect used if none has been supplied.
		# Prefer your clients to pre register a redirect uri rather than
		# supplying one on each authorization request.
		redirect_uri = frappe.db.get_value("OAuth Client", client_id, "default_redirect_uri")
		return redirect_uri

	def validate_scopes(self, client_id, scopes, client, request, *args, **kwargs):
		# Is the client allowed to access the requested scopes?
		allowed_scopes = get_client_scopes(client_id)
		return all(scope in allowed_scopes for scope in scopes)

	def get_default_scopes(self, client_id, request, *args, **kwargs):
		# Scopes a client will authorize for if none are supplied in the
		# authorization request.
		scopes = get_client_scopes(client_id)
		request.scopes = scopes  # Apparently this is possible.
		return scopes

	def validate_response_type(self, client_id, response_type, client, request, *args, **kwargs):
		allowed_response_types = [
			# From OAuth Client response_type field
			client.response_type.lower(),
			# OIDC
			"id_token",
			"id_token token",
			"code id_token",
			"code token id_token",
		]

		return response_type in allowed_response_types

	# Post-authorization

	def save_authorization_code(self, client_id, code, request, *args, **kwargs):

		cookie_dict = get_cookie_dict_from_headers(request)

		oac = frappe.new_doc("OAuth Authorization Code")
		oac.scopes = get_url_delimiter().join(request.scopes)
		oac.redirect_uri_bound_to_authorization_code = request.redirect_uri
		oac.client = client_id
		oac.user = unquote(cookie_dict["user_id"].value)
		oac.authorization_code = code["code"]

		if request.nonce:
			oac.nonce = request.nonce

		if request.code_challenge and request.code_challenge_method:
			oac.code_challenge = request.code_challenge
			oac.code_challenge_method = request.code_challenge_method.lower()

		oac.save(ignore_permissions=True)
		frappe.db.commit()

	def authenticate_client(self, request, *args, **kwargs):
		# Get ClientID in URL
		if request.client_id:
			oc = frappe.get_doc("OAuth Client", request.client_id)
		else:
			# Extract token, instantiate OAuth Bearer Token and use clientid from there.
			if "refresh_token" in frappe.form_dict:
				oc = frappe.get_doc(
					"OAuth Client",
					frappe.db.get_value(
						"OAuth Bearer Token",
						{"refresh_token": frappe.form_dict["refresh_token"]},
						"client",
					),
				)
			elif "token" in frappe.form_dict:
				oc = frappe.get_doc(
					"OAuth Client",
					frappe.db.get_value("OAuth Bearer Token", frappe.form_dict["token"], "client"),
				)
			else:
				oc = frappe.get_doc(
					"OAuth Client",
					frappe.db.get_value(
						"OAuth Bearer Token",
						frappe.get_request_header("Authorization").split(" ")[1],
						"client",
					),
				)
		try:
			request.client = request.client or oc.as_dict()
		except Exception as e:
			return generate_json_error_response(e)

		cookie_dict = get_cookie_dict_from_headers(request)
		user_id = unquote(cookie_dict.get("user_id").value) if "user_id" in cookie_dict else "Guest"
		return frappe.session.user == user_id

	def authenticate_client_id(self, client_id, request, *args, **kwargs):
		cli_id = frappe.db.get_value("OAuth Client", client_id, "name")
		if not cli_id:
			# Don't allow public (non-authenticated) clients
			return False
		else:
			request["client"] = frappe.get_doc("OAuth Client", cli_id)
			return True

	def validate_code(self, client_id, code, client, request, *args, **kwargs):
		# Validate the code belongs to the client. Add associated scopes,
		# state and user to request.scopes and request.user.

		validcodes = frappe.get_all(
			"OAuth Authorization Code",
			filters={"client": client_id, "validity": "Valid"},
		)

		checkcodes = []
		for vcode in validcodes:
			checkcodes.append(vcode["name"])

		if code in checkcodes:
			request.scopes = frappe.db.get_value("OAuth Authorization Code", code, "scopes").split(
				get_url_delimiter()
			)
			request.user = frappe.db.get_value("OAuth Authorization Code", code, "user")
			code_challenge_method = frappe.db.get_value(
				"OAuth Authorization Code", code, "code_challenge_method"
			)
			code_challenge = frappe.db.get_value("OAuth Authorization Code", code, "code_challenge")

			if code_challenge and not request.code_verifier:
				if frappe.db.exists("OAuth Authorization Code", code):
					frappe.delete_doc("OAuth Authorization Code", code, ignore_permissions=True)
					frappe.db.commit()
				return False

			if code_challenge_method == "s256":
				m = hashlib.sha256()
				m.update(bytes(request.code_verifier, "utf-8"))
				code_verifier = base64.b64encode(m.digest()).decode("utf-8")
				code_verifier = re.sub(r"\+", "-", code_verifier)
				code_verifier = re.sub(r"\/", "_", code_verifier)
				code_verifier = re.sub(r"=", "", code_verifier)
				return code_challenge == code_verifier

			elif code_challenge_method == "plain":
				return code_challenge == request.code_verifier

			return True

		return False

	def confirm_redirect_uri(self, client_id, code, redirect_uri, client, *args, **kwargs):
		saved_redirect_uri = frappe.db.get_value("OAuth Client", client_id, "default_redirect_uri")

		redirect_uris = frappe.db.get_value("OAuth Client", client_id, "redirect_uris")

		if redirect_uris:
			redirect_uris = redirect_uris.split(get_url_delimiter())
			return redirect_uri in redirect_uris

		return saved_redirect_uri == redirect_uri

	def validate_grant_type(self, client_id, grant_type, client, request, *args, **kwargs):
		# Clients should only be allowed to use one type of grant.
		# In this case, it must be "authorization_code" or "refresh_token"
		return grant_type in ["authorization_code", "refresh_token", "password"]

	def save_bearer_token(self, token, request, *args, **kwargs):
		# Remember to associate it with request.scopes, request.user and
		# request.client. The two former will be set when you validate
		# the authorization code. Don't forget to save both the
		# access_token and the refresh_token and set expiration for the
		# access_token to now + expires_in seconds.

		otoken = frappe.new_doc("OAuth Bearer Token")
		otoken.client = request.client["name"]
		try:
			otoken.user = (
				request.user
				if request.user
				else frappe.db.get_value(
					"OAuth Bearer Token",
					{"refresh_token": request.body.get("refresh_token")},
					"user",
				)
			)
		except Exception:
			otoken.user = frappe.session.user

		otoken.scopes = get_url_delimiter().join(request.scopes)
		otoken.access_token = token["access_token"]
		otoken.refresh_token = token.get("refresh_token")
		otoken.expires_in = token["expires_in"]
		otoken.save(ignore_permissions=True)
		frappe.db.commit()

		default_redirect_uri = frappe.db.get_value(
			"OAuth Client", request.client["name"], "default_redirect_uri"
		)
		return default_redirect_uri

	def invalidate_authorization_code(self, client_id, code, request, *args, **kwargs):
		# Authorization codes are use once, invalidate it when a Bearer token
		# has been acquired.

		frappe.db.set_value("OAuth Authorization Code", code, "validity", "Invalid")
		frappe.db.commit()

	# Protected resource request

	def validate_bearer_token(self, token, scopes, request):
		# Remember to check expiration and scope membership
		otoken = frappe.get_doc("OAuth Bearer Token", token)
		is_token_valid = (now_datetime() < otoken.expiration_time) and otoken.status != "Revoked"
		client_scopes = frappe.db.get_value("OAuth Client", otoken.client, "scopes").split(
			get_url_delimiter()
		)
		are_scopes_valid = True
		for scp in scopes:
			are_scopes_valid = are_scopes_valid and True if scp in client_scopes else False

		return is_token_valid and are_scopes_valid

	# Token refresh request

	def get_original_scopes(self, refresh_token, request, *args, **kwargs):
		# Obtain the token associated with the given refresh_token and
		# return its scopes, these will be passed on to the refreshed
		# access token if the client did not specify a scope during the
		# request.
		obearer_token = frappe.get_doc("OAuth Bearer Token", {"refresh_token": refresh_token})
		return obearer_token.scopes

	def revoke_token(self, token, token_type_hint, request, *args, **kwargs):
		"""Revoke an access or refresh token.

		:param token: The token string.
		:param token_type_hint: access_token or refresh_token.
		:param request: The HTTP Request (oauthlib.common.Request)

		Method is used by:
		- Revocation Endpoint
		"""
		if token_type_hint == "access_token":
			frappe.db.set_value("OAuth Bearer Token", token, "status", "Revoked")
		elif token_type_hint == "refresh_token":
			frappe.db.set_value("OAuth Bearer Token", {"refresh_token": token}, "status", "Revoked")
		else:
			frappe.db.set_value("OAuth Bearer Token", token, "status", "Revoked")
		frappe.db.commit()

	def validate_refresh_token(self, refresh_token, client, request, *args, **kwargs):
		"""Ensure the Bearer token is valid and authorized access to scopes.

		OBS! The request.user attribute should be set to the resource owner
		associated with this refresh token.

		:param refresh_token: Unicode refresh token
		:param client: Client object set by you, see authenticate_client.
		:param request: The HTTP Request (oauthlib.common.Request)
		:rtype: True or False

		Method is used by:
		- Authorization Code Grant (indirectly by issuing refresh tokens)
		- Resource Owner Password Credentials Grant (also indirectly)
		- Refresh Token Grant
		"""

		otoken = frappe.get_doc(
			"OAuth Bearer Token", {"refresh_token": refresh_token, "status": "Active"}
		)

		if not otoken:
			return False
		else:
			return True

	# OpenID Connect

	def finalize_id_token(self, id_token, token, token_handler, request):
		# Check whether frappe server URL is set
		id_token_header = {"typ": "jwt", "alg": "HS256"}

		user = frappe.get_doc("User", request.user)

		if request.nonce:
			id_token["nonce"] = request.nonce

		userinfo = get_userinfo(user)

		id_token["exp"] = id_token.get("iat") + token.get("expires_in")

		if userinfo.get("iss"):
			id_token["iss"] = userinfo.get("iss")

		if "openid" in request.scopes:
			id_token.update(userinfo)

		id_token_encoded = jwt.encode(
			payload=id_token,
			key=request.client.client_secret,
			algorithm="HS256",
			headers=id_token_header,
		)

		return frappe.safe_decode(id_token_encoded)

	def get_authorization_code_nonce(self, client_id, code, redirect_uri, request):
		if frappe.get_value("OAuth Authorization Code", code, "validity") == "Valid":
			return frappe.get_value("OAuth Authorization Code", code, "nonce")

		return None

	def get_authorization_code_scopes(self, client_id, code, redirect_uri, request):
		scope = frappe.get_value("OAuth Client", client_id, "scopes")
		if not scope:
			scope = []
		else:
			scope = scope.split(get_url_delimiter())

		return scope

	def get_jwt_bearer_token(self, token, token_handler, request):
		now = datetime.datetime.now()

		id_token = dict(
			aud=token.client_id,
			iat=round(now.timestamp()),
			at_hash=calculate_at_hash(token.access_token, hashlib.sha256),
		)
		return self.finalize_id_token(id_token, token, token_handler, request)

	def get_userinfo_claims(self, request):
		user = frappe.get_doc("User", frappe.session.user)
		userinfo = get_userinfo(user)
		return userinfo

	def validate_id_token(self, token, scopes, request):
		try:
			id_token = frappe.get_doc("OAuth Bearer Token", token)
			if id_token.status == "Active":
				return True
		except Exception:
			return False

		return False

	def validate_jwt_bearer_token(self, token, scopes, request):
		try:
			jwt = frappe.get_doc("OAuth Bearer Token", token)
			if jwt.status == "Active":
				return True
		except Exception:
			return False

		return False

	def validate_silent_authorization(self, request):
		"""Ensure the logged in user has authorized silent OpenID authorization.

		Silent OpenID authorization allows access tokens and id tokens to be
		granted to clients without any user prompt or interaction.

		:param request: The HTTP Request (oauthlib.common.Request)
		:rtype: True or False

		Method is used by:
		- OpenIDConnectAuthCode
		- OpenIDConnectImplicit
		- OpenIDConnectHybrid
		"""
		if request.prompt == "login":
			return False
		else:
			return True

	def validate_silent_login(self, request):
		"""Ensure session user has authorized silent OpenID login.

		If no user is logged in or has not authorized silent login, this
		method should return False.

		If the user is logged in but associated with multiple accounts and
		not selected which one to link to the token then this method should
		raise an oauthlib.oauth2.AccountSelectionRequired error.

		:param request: The HTTP Request (oauthlib.common.Request)
		:rtype: True or False

		Method is used by:
		- OpenIDConnectAuthCode
		- OpenIDConnectImplicit
		- OpenIDConnectHybrid
		"""
		if frappe.session.user == "Guest" or request.prompt.lower() == "login":
			return False
		else:
			return True

	def validate_user_match(self, id_token_hint, scopes, claims, request):
		"""Ensure client supplied user id hint matches session user.

		If the sub claim or id_token_hint is supplied then the session
		user must match the given ID.

		:param id_token_hint: User identifier string.
		:param scopes: List of OAuth 2 scopes and OpenID claims (strings).
		:param claims: OpenID Connect claims dict.
		:param request: The HTTP Request (oauthlib.common.Request)
		:rtype: True or False

		Method is used by:
		- OpenIDConnectAuthCode
		- OpenIDConnectImplicit
		- OpenIDConnectHybrid
		"""
		if id_token_hint:
			try:
				user = None
				payload = jwt.decode(
					id_token_hint,
					algorithms=["HS256"],
					options={
						"verify_signature": False,
						"verify_aud": False,
					},
				)
				client_id, client_secret = frappe.get_value(
					"OAuth Client",
					payload.get("aud"),
					["client_id", "client_secret"],
				)

				if payload.get("sub") and client_id and client_secret:
					user = frappe.db.get_value(
						"User Social Login",
						{"userid": payload.get("sub"), "provider": "frappe"},
						"parent",
					)
					user = frappe.get_doc("User", user)
					verified_payload = jwt.decode(
						id_token_hint,
						key=client_secret,
						audience=client_id,
						algorithms=["HS256"],
						options={
							"verify_exp": False,
						},
					)

					if verified_payload:
						return user.name == frappe.session.user

			except Exception:
				return False

		elif frappe.session.user != "Guest":
			return True

		return False

	def validate_user(self, username, password, client, request, *args, **kwargs):
		"""Ensure the username and password is valid.

		Method is used by:
		- Resource Owner Password Credentials Grant
		"""
		login_manager = LoginManager()
		login_manager.authenticate(username, password)

		if login_manager.user == "Guest":
			return False

		request.user = login_manager.user
		return True


def get_cookie_dict_from_headers(r):
	cookie = cookies.BaseCookie()
	if r.headers.get("Cookie"):
		cookie.load(r.headers.get("Cookie"))
	return cookie


def calculate_at_hash(access_token, hash_alg):
	"""Helper method for calculating an access token
	hash, as described in http://openid.net/specs/openid-connect-core-1_0.html#CodeIDToken
	Its value is the base64url encoding of the left-most half of the hash of the octets
	of the ASCII representation of the access_token value, where the hash algorithm
	used is the hash algorithm used in the alg Header Parameter of the ID Token's JOSE
	Header. For instance, if the alg is RS256, hash the access_token value with SHA-256,
	then take the left-most 128 bits and base64url encode them. The at_hash value is a
	case sensitive string.
	Args:
	access_token (str): An access token string.
	hash_alg (callable): A callable returning a hash object, e.g. hashlib.sha256
	"""
	hash_digest = hash_alg(access_token.encode("utf-8")).digest()
	cut_at = int(len(hash_digest) / 2)
	truncated = hash_digest[:cut_at]
	from jwt.utils import base64url_encode

	at_hash = base64url_encode(truncated)
	return at_hash.decode("utf-8")


def delete_oauth2_data():
	# Delete Invalid Authorization Code and Revoked Token
	commit_code, commit_token = False, False
	code_list = frappe.get_all("OAuth Authorization Code", filters={"validity": "Invalid"})
	token_list = frappe.get_all("OAuth Bearer Token", filters={"status": "Revoked"})
	if len(code_list) > 0:
		commit_code = True
	if len(token_list) > 0:
		commit_token = True
	for code in code_list:
		frappe.delete_doc("OAuth Authorization Code", code["name"])
	for token in token_list:
		frappe.delete_doc("OAuth Bearer Token", token["name"])
	if commit_code or commit_token:
		frappe.db.commit()


def get_client_scopes(client_id):
	scopes_string = frappe.db.get_value("OAuth Client", client_id, "scopes")
	return scopes_string.split()


def get_userinfo(user):
	picture = None
	frappe_server_url = get_server_url()
	valid_url_schemes = ("http", "https", "ftp", "ftps")

	if user.user_image:
		if frappe.utils.validate_url(user.user_image, valid_schemes=valid_url_schemes):
			picture = user.user_image
		else:
			picture = urljoin(frappe_server_url, user.user_image)

	userinfo = frappe._dict(
		{
			"sub": frappe.db.get_value(
				"User Social Login",
				{"parent": user.name, "provider": "frappe"},
				"userid",
			),
			"name": " ".join(filter(None, [user.first_name, user.last_name])),
			"given_name": user.first_name,
			"family_name": user.last_name,
			"email": user.email,
			"picture": picture,
			"roles": frappe.get_roles(user.name),
			"iss": frappe_server_url,
		}
	)

	return userinfo


def get_url_delimiter(separator_character=" "):
	return separator_character


def generate_json_error_response(e):
	if not e:
		e = frappe._dict({})

	frappe.local.response = frappe._dict(
		{
			"description": getattr(e, "description", "Internal Server Error"),
			"status_code": getattr(e, "status_code", 500),
			"error": getattr(e, "error", "internal_server_error"),
		}
	)
	frappe.local.response["http_status_code"] = getattr(e, "status_code", 500)
	return


def get_server_url():
	request_url = urlparse(frappe.request.url)
	request_url = f"{request_url.scheme}://{request_url.netloc}"
	return frappe.get_value("Social Login Key", "frappe", "base_url") or request_url
