from __future__ import print_function, unicode_literals
import frappe
import pytz

from frappe import _
from frappe.auth import LoginManager
from oauthlib.oauth2.rfc6749.tokens import BearerToken
from oauthlib.oauth2.rfc6749.grant_types import AuthorizationCodeGrant, ImplicitGrant, ResourceOwnerPasswordCredentialsGrant, ClientCredentialsGrant,  RefreshTokenGrant
from oauthlib.oauth2 import RequestValidator
from oauthlib.oauth2.rfc6749.endpoints.authorization import AuthorizationEndpoint
from oauthlib.oauth2.rfc6749.endpoints.token import TokenEndpoint
from oauthlib.oauth2.rfc6749.endpoints.resource import ResourceEndpoint
from oauthlib.oauth2.rfc6749.endpoints.revocation import RevocationEndpoint
from oauthlib.common import Request
from six.moves.urllib.parse import parse_qs, urlparse, unquote

def get_url_delimiter(separator_character=" "):
	return separator_character

class WebApplicationServer(AuthorizationEndpoint, TokenEndpoint, ResourceEndpoint,
						   RevocationEndpoint):

	"""An all-in-one endpoint featuring Authorization code grant and Bearer tokens."""

	def __init__(self, request_validator, token_generator=None,
				 token_expires_in=None, refresh_token_generator=None, **kwargs):
		"""Construct a new web application server.

		:param request_validator: An implementation of
								  oauthlib.oauth2.RequestValidator.
		:param token_expires_in: An int or a function to generate a token
								 expiration offset (in seconds) given a
								 oauthlib.common.Request object.
		:param token_generator: A function to generate a token from a request.
		:param refresh_token_generator: A function to generate a token from a
										request for the refresh token.
		:param kwargs: Extra parameters to pass to authorization-,
					   token-, resource-, and revocation-endpoint constructors.
		"""
		implicit_grant = ImplicitGrant(request_validator)
		auth_grant = AuthorizationCodeGrant(request_validator)
		refresh_grant = RefreshTokenGrant(request_validator)
		resource_owner_password_credentials_grant = ResourceOwnerPasswordCredentialsGrant(request_validator)
		bearer = BearerToken(request_validator, token_generator,
							 token_expires_in, refresh_token_generator)
		AuthorizationEndpoint.__init__(self, default_response_type='code',
									   response_types={
											'code': auth_grant,
											'token': implicit_grant
										},
									   default_token_type=bearer)
		TokenEndpoint.__init__(self, default_grant_type='authorization_code',
							   grant_types={
								   'authorization_code': auth_grant,
								   'refresh_token': refresh_grant,
								   'password': resource_owner_password_credentials_grant
							   },
							   default_token_type=bearer)
		ResourceEndpoint.__init__(self, default_token='Bearer',
								  token_types={'Bearer': bearer})
		RevocationEndpoint.__init__(self, request_validator)


class OAuthWebRequestValidator(RequestValidator):

	# Pre- and post-authorization.
	def validate_client_id(self, client_id, request, *args, **kwargs):
		# Simple validity check, does client exist? Not banned?
		cli_id = frappe.db.get_value("OAuth Client",{ "name":client_id })
		if cli_id:
			request.client = frappe.get_doc("OAuth Client", client_id).as_dict()
			return True
		else:
			return False

	def validate_redirect_uri(self, client_id, redirect_uri, request, *args, **kwargs):
		# Is the client allowed to use the supplied redirect_uri? i.e. has
		# the client previously registered this EXACT redirect uri.

		redirect_uris = frappe.db.get_value("OAuth Client", client_id, 'redirect_uris').split(get_url_delimiter())

		if redirect_uri in redirect_uris:
			return True
		else:
			return False

	def get_default_redirect_uri(self, client_id, request, *args, **kwargs):
		# The redirect used if none has been supplied.
		# Prefer your clients to pre register a redirect uri rather than
		# supplying one on each authorization request.
		redirect_uri = frappe.db.get_value("OAuth Client", client_id, 'default_redirect_uri')
		return redirect_uri

	def validate_scopes(self, client_id, scopes, client, request, *args, **kwargs):
		# Is the client allowed to access the requested scopes?
		client_scopes = frappe.db.get_value("OAuth Client", client_id, 'scopes').split(get_url_delimiter())

		are_scopes_valid = True

		for scp in scopes:
			are_scopes_valid = are_scopes_valid and True if scp in client_scopes else False

		return are_scopes_valid

	def get_default_scopes(self, client_id, request, *args, **kwargs):
		# Scopes a client will authorize for if none are supplied in the
		# authorization request.
		scopes = frappe.db.get_value("OAuth Client", client_id, 'scopes').split(get_url_delimiter())
		request.scopes = scopes #Apparently this is possible.
		return scopes

	def validate_response_type(self, client_id, response_type, client, request, *args, **kwargs):
		# Clients should only be allowed to use one type of response type, the
		# one associated with their one allowed grant type.
		# In this case it must be "code".
		allowed_response_types = [client.response_type.lower(),
			"code token", "code id_token", "code token id_token",
			"code+token", "code+id_token", "code+token id_token"]

		return (response_type in allowed_response_types)


	# Post-authorization

	def save_authorization_code(self, client_id, code, request, *args, **kwargs):

		cookie_dict = get_cookie_dict_from_headers(request)

		oac = frappe.new_doc('OAuth Authorization Code')
		oac.scopes = get_url_delimiter().join(request.scopes)
		oac.redirect_uri_bound_to_authorization_code = request.redirect_uri
		oac.client = client_id
		oac.user = unquote(cookie_dict['user_id'])
		oac.authorization_code = code['code']
		oac.save(ignore_permissions=True)
		frappe.db.commit()

	def authenticate_client(self, request, *args, **kwargs):

		cookie_dict = get_cookie_dict_from_headers(request)

		#Get ClientID in URL
		if request.client_id:
			oc = frappe.get_doc("OAuth Client", request.client_id)
		else:
			#Extract token, instantiate OAuth Bearer Token and use clientid from there.
			if "refresh_token" in frappe.form_dict:
				oc = frappe.get_doc("OAuth Client", frappe.db.get_value("OAuth Bearer Token", {"refresh_token": frappe.form_dict["refresh_token"]}, 'client'))
			elif "token" in frappe.form_dict:
				oc = frappe.get_doc("OAuth Client", frappe.db.get_value("OAuth Bearer Token", frappe.form_dict["token"], 'client'))
			else:
				oc = frappe.get_doc("OAuth Client", frappe.db.get_value("OAuth Bearer Token", frappe.get_request_header("Authorization").split(" ")[1], 'client'))
		try:
			request.client = request.client or oc.as_dict()
		except Exception as e:
			print("Failed body authentication: Application %s does not exist".format(cid=request.client_id))

		return frappe.session.user == unquote(cookie_dict.get('user_id', "Guest"))

	def authenticate_client_id(self, client_id, request, *args, **kwargs):
		cli_id = frappe.db.get_value('OAuth Client', client_id, 'name')
		if not cli_id:
			# Don't allow public (non-authenticated) clients
			return False
		else:
			request["client"] = frappe.get_doc("OAuth Client", cli_id)
			return True

	def validate_code(self, client_id, code, client, request, *args, **kwargs):
		# Validate the code belongs to the client. Add associated scopes,
		# state and user to request.scopes and request.user.

		validcodes = frappe.get_all("OAuth Authorization Code", filters={"client": client_id, "validity": "Valid"})

		checkcodes = []
		for vcode in validcodes:
			checkcodes.append(vcode["name"])

		if code in checkcodes:
			request.scopes = frappe.db.get_value("OAuth Authorization Code", code, 'scopes').split(get_url_delimiter())
			request.user = frappe.db.get_value("OAuth Authorization Code", code, 'user')
			return True
		else:
			return False

	def confirm_redirect_uri(self, client_id, code, redirect_uri, client, *args, **kwargs):
		saved_redirect_uri = frappe.db.get_value('OAuth Client', client_id, 'default_redirect_uri')

		return saved_redirect_uri == redirect_uri

	def validate_grant_type(self, client_id, grant_type, client, request, *args, **kwargs):
		# Clients should only be allowed to use one type of grant.
		# In this case, it must be "authorization_code" or "refresh_token"
		return (grant_type in ["authorization_code", "refresh_token", "password"])

	def save_bearer_token(self, token, request, *args, **kwargs):
		# Remember to associate it with request.scopes, request.user and
		# request.client. The two former will be set when you validate
		# the authorization code. Don't forget to save both the
		# access_token and the refresh_token and set expiration for the
		# access_token to now + expires_in seconds.

		otoken = frappe.new_doc("OAuth Bearer Token")
		otoken.client = request.client['name']
		try:
			otoken.user = request.user if request.user else frappe.db.get_value("OAuth Bearer Token", {"refresh_token":request.body.get("refresh_token")}, "user")
		except Exception as e:
			otoken.user = frappe.session.user
		otoken.scopes = get_url_delimiter().join(request.scopes)
		otoken.access_token = token['access_token']
		otoken.refresh_token = token.get('refresh_token')
		otoken.expires_in = token['expires_in']
		otoken.save(ignore_permissions=True)
		frappe.db.commit()

		default_redirect_uri = frappe.db.get_value("OAuth Client", request.client['name'], "default_redirect_uri")
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
		token_expiration_local = otoken.expiration_time.replace(tzinfo=pytz.timezone(frappe.utils.get_time_zone()))
		token_expiration_utc = token_expiration_local.astimezone(pytz.utc)
		is_token_valid = (frappe.utils.datetime.datetime.utcnow().replace(tzinfo=pytz.utc) < token_expiration_utc) \
			and otoken.status != "Revoked"
		client_scopes = frappe.db.get_value("OAuth Client", otoken.client, 'scopes').split(get_url_delimiter())
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
		otoken = None

		if token_type_hint == "access_token":
			otoken = frappe.db.set_value("OAuth Bearer Token", token, 'status', 'Revoked')
		elif token_type_hint == "refresh_token":
			otoken = frappe.db.set_value("OAuth Bearer Token", {"refresh_token": token}, 'status', 'Revoked')
		else:
			otoken = frappe.db.set_value("OAuth Bearer Token", token, 'status', 'Revoked')
		frappe.db.commit()

	def validate_refresh_token(self, refresh_token, client, request, *args, **kwargs):
			# """Ensure the Bearer token is valid and authorized access to scopes.

			# OBS! The request.user attribute should be set to the resource owner
			# associated with this refresh token.

			# :param refresh_token: Unicode refresh token
			# :param client: Client object set by you, see authenticate_client.
			# :param request: The HTTP Request (oauthlib.common.Request)
			# :rtype: True or False

			# Method is used by:
			# 	- Authorization Code Grant (indirectly by issuing refresh tokens)
			# 	- Resource Owner Password Credentials Grant (also indirectly)
			# 	- Refresh Token Grant
			# """

		otoken = frappe.get_doc("OAuth Bearer Token", {"refresh_token": refresh_token, "status": "Active"})

		if not otoken:
			return False
		else:
			return True

	# OpenID Connect
	def get_id_token(self, token, token_handler, request):
		"""
		In the OpenID Connect workflows when an ID Token is requested this method is called.
		Subclasses should implement the construction, signing and optional encryption of the
		ID Token as described in the OpenID Connect spec.

		In addition to the standard OAuth2 request properties, the request may also contain
		these OIDC specific properties which are useful to this method:

		    - nonce, if workflow is implicit or hybrid and it was provided
		    - claims, if provided to the original Authorization Code request

		The token parameter is a dict which may contain an ``access_token`` entry, in which
		case the resulting ID Token *should* include a calculated ``at_hash`` claim.

		Similarly, when the request parameter has a ``code`` property defined, the ID Token
		*should* include a calculated ``c_hash`` claim.

		http://openid.net/specs/openid-connect-core-1_0.html (sections `3.1.3.6`_, `3.2.2.10`_, `3.3.2.11`_)

		.. _`3.1.3.6`: http://openid.net/specs/openid-connect-core-1_0.html#CodeIDToken
		.. _`3.2.2.10`: http://openid.net/specs/openid-connect-core-1_0.html#ImplicitIDToken
		.. _`3.3.2.11`: http://openid.net/specs/openid-connect-core-1_0.html#HybridIDToken

		:param token: A Bearer token dict
		:param token_handler: the token handler (BearerToken class)
		:param request: the HTTP Request (oauthlib.common.Request)
		:return: The ID Token (a JWS signed JWT)
		"""
		# the request.scope should be used by the get_id_token() method to determine which claims to include in the resulting id_token

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
			False
		else:
			True

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
		if id_token_hint and id_token_hint == frappe.db.get_value("User Social Login", {"parent":frappe.session.user, "provider": "frappe"}, "userid"):
			return True
		else:
			return False

	def validate_user(self, username, password, client, request, *args, **kwargs):
		"""Ensure the username and password is valid.

        Method is used by:
            - Resource Owner Password Credentials Grant
        """
		login_manager = LoginManager()
		login_manager.authenticate(username, password)
		request.user = login_manager.user
		return True

def get_cookie_dict_from_headers(r):
	if r.headers.get('Cookie'):
		cookie = r.headers.get('Cookie')
		cookie = cookie.split("; ")
		cookie_dict = {k:v for k,v in (x.split('=') for x in cookie)}
		return cookie_dict
	else:
		return {}

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
	hash_digest = hash_alg(access_token.encode('utf-8')).digest()
	cut_at = int(len(hash_digest) / 2)
	truncated = hash_digest[:cut_at]
	from jwt.utils import base64url_encode
	at_hash = base64url_encode(truncated)
	return at_hash.decode('utf-8')

def delete_oauth2_data():
	# Delete Invalid Authorization Code and Revoked Token
	commit_code, commit_token = False, False
	code_list = frappe.get_all("OAuth Authorization Code", filters={"validity":"Invalid"})
	token_list = frappe.get_all("OAuth Bearer Token", filters={"status":"Revoked"})
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
