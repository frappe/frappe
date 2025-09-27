import json
import re
import uuid
from urllib.parse import urlparse

from webauthn import (
	generate_authentication_options,
	generate_registration_options,
	verify_authentication_response,
	verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url, generate_user_handle
from webauthn.helpers.options_to_json_dict import options_to_json_dict
from webauthn.helpers.structs import (
	AuthenticatorSelectionCriteria,
	PublicKeyCredentialDescriptor,
	PublicKeyCredentialType,
	ResidentKeyRequirement,
	UserVerificationRequirement,
)

import frappe
from frappe import _
from frappe.auth import LoginManager

# Constants
MAX_PASSKEYS_PER_USER = 3
CHALLENGE_EXPIRY_SECONDS = 300
PASSKEY_BATCH_SIZE = 1000


def _sanitize_cache_key(key: str) -> str:
	"""Sanitize cache key to prevent path traversal"""
	return re.sub(r"[^a-zA-Z0-9_@.-]", "_", key)


def _validate_user_access(user: str) -> None:
	"""Validate user exists and current user has access"""
	if not user:
		frappe.throw(_("User is required"))

	if not frappe.db.exists("User", user):
		frappe.throw(_("Invalid user"))

	# Only allow users to manage their own passkeys (except System Manager)
	if user != frappe.session.user and not frappe.has_permission("User", "write"):
		frappe.throw(_("Access denied"))


def _validate_passkey_registration(email: str) -> list:
	"""Validate user can register new passkey and return existing passkeys"""
	_validate_user_access(email)

	user_active_passkeys = frappe.get_all(
		"User Passkey", filters={"user": email, "status": "Active"}, fields=["credential_id"]
	)

	if len(user_active_passkeys) >= MAX_PASSKEYS_PER_USER:
		frappe.throw(
			_("You can have a maximum of {0} active passkeys. Revoke an old one to add a new device.").format(
				MAX_PASSKEYS_PER_USER
			)
		)

	return user_active_passkeys


def _get_or_create_user_id(email: str) -> bytes:
	"""Get or create passkey user ID for the user"""
	user = frappe.get_doc("User", email)
	return base64url_to_bytes(user.get_passkey_user_id())


def _create_exclude_credentials(user_active_passkeys: list) -> list:
	"""Create exclude credentials list for registration"""
	return [
		PublicKeyCredentialDescriptor(
			id=base64url_to_bytes(cred.credential_id), type=PublicKeyCredentialType.PUBLIC_KEY
		)
		for cred in user_active_passkeys
	]


@frappe.whitelist()
def register_challenge(email: str, user_display_name: str):
	"""Generate passkey registration challenge"""
	try:
		if not email or not user_display_name:
			return {"success": False, "error": _("Email and display name are required")}

		user_active_passkeys = _validate_passkey_registration(email)
		user_id = _get_or_create_user_id(email)
		exclude_credentials = _create_exclude_credentials(user_active_passkeys)

		authenticator_selection = AuthenticatorSelectionCriteria(
			resident_key=ResidentKeyRequirement.DISCOURAGED,
			user_verification=UserVerificationRequirement.PREFERRED,
		)

		registration_options = generate_registration_options(
			rp_id=urlparse(frappe.utils.get_url()).hostname,
			rp_name="Frappe",
			user_name=email,
			user_id=user_id,
			user_display_name=user_display_name,
			exclude_credentials=exclude_credentials,
			authenticator_selection=authenticator_selection,
		)

		cache_key = f"passkey_challenge:{_sanitize_cache_key(email)}"
		frappe.cache().set(cache_key, registration_options.challenge, CHALLENGE_EXPIRY_SECONDS)

		return options_to_json_dict(registration_options)

	except frappe.ValidationError:
		raise
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Passkey Registration Challenge Failed")
		return {"success": False, "error": _("Failed to generate registration challenge")}


@frappe.whitelist()
def register_verify(email: str, credential):
	"""Verify passkey registration"""
	try:
		if not email:
			return {"success": False, "error": _("Email is required")}

		_validate_user_access(email)

		if isinstance(credential, str):
			credential = json.loads(credential)

		cache_key = f"passkey_challenge:{_sanitize_cache_key(email)}"
		expected_challenge = frappe.cache().get(cache_key)
		if not expected_challenge:
			return {"success": False, "error": _("Registration challenge not found or expired")}

		verified_credential = verify_registration_response(
			credential=credential,
			expected_challenge=expected_challenge,
			expected_rp_id=urlparse(frappe.utils.get_url()).hostname,
			expected_origin=frappe.utils.get_url(),
			require_user_verification=True,
		)

		if verified_credential:
			credential_id = bytes_to_base64url(verified_credential.credential_id)

			# Check if credential already exists
			if frappe.db.exists("User Passkey", {"credential_id": credential_id, "user": email}):
				return {"success": False, "error": _("This passkey is already registered")}

			# Create new passkey record
			passkey = frappe.new_doc("User Passkey")
			passkey.user = email
			passkey.credential_id = credential_id
			passkey.public_key = bytes_to_base64url(verified_credential.credential_public_key)
			passkey.sign_count = verified_credential.sign_count
			passkey.title = credential.get("title", _("Unnamed Passkey"))
			passkey.flags.ignore_permissions = True
			passkey.insert()

			# Clear challenge from cache
			frappe.cache().delete(cache_key)

			return {"success": True, "credential_id": credential_id}

		return {"success": False, "error": _("Credential verification failed")}

	except frappe.ValidationError:
		raise
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Passkey Registration Verify Failed")
		return {"success": False, "error": _("Registration verification failed")}


def _get_all_active_passkeys():
	"""Get all active passkeys with pagination fallback"""
	passkeys = []
	start = 0

	while True:
		batch = frappe.get_all(
			"User Passkey",
			filters={"status": "Active"},
			fields=["credential_id"],
			limit=PASSKEY_BATCH_SIZE,
			start=start,
			order_by="creation desc",
		)

		if not batch:
			break

		passkeys.extend(batch)
		start += PASSKEY_BATCH_SIZE

		# Safety limit to prevent infinite loops
		if len(passkeys) > 50000:  # Reasonable upper limit
			frappe.log_error("Too many active passkeys detected", "Passkey Login Challenge")
			break

	return passkeys


@frappe.whitelist(allow_guest=True)
def login_challenge():
	"""Generate passkey authentication challenge"""
	try:
		active_passkeys = _get_all_active_passkeys()

		allow_credentials = [
			PublicKeyCredentialDescriptor(
				id=base64url_to_bytes(d["credential_id"]), type=PublicKeyCredentialType.PUBLIC_KEY
			)
			for d in active_passkeys
		]

		auth_options = generate_authentication_options(
			rp_id=urlparse(frappe.utils.get_url()).hostname, allow_credentials=allow_credentials
		)

		# Use UUID for cache key to avoid user enumeration
		cache_id = str(uuid.uuid4())
		cache_key = f"passkey_challenge:{_sanitize_cache_key(cache_id)}"
		frappe.cache().set(cache_key, auth_options.challenge, CHALLENGE_EXPIRY_SECONDS)

		response = options_to_json_dict(auth_options)
		response["cache_id"] = cache_id
		return response

	except Exception:
		frappe.log_error(frappe.get_traceback(), "Passkey Login Challenge Failed")
		return {"success": False, "error": _("Failed to generate login challenge")}


@frappe.whitelist(allow_guest=True)
def login_verify(credential_response):
	"""Verify passkey authentication"""
	try:
		if isinstance(credential_response, str):
			credential_response = json.loads(credential_response)

		cache_id = credential_response.get("cache_id")
		if not cache_id:
			return {"success": False, "error": _("Invalid authentication request")}

		cache_key = f"passkey_challenge:{_sanitize_cache_key(cache_id)}"
		expected_challenge = frappe.cache().get(cache_key)
		if not expected_challenge:
			return {"success": False, "error": _("Login challenge not found or expired")}

		credential_id = credential_response.get("id")
		if not credential_id:
			return {"success": False, "error": _("Invalid credential")}

		try:
			passkey_doc = frappe.get_doc("User Passkey", {"credential_id": credential_id})
		except frappe.DoesNotExistError:
			return {"success": False, "error": _("Passkey not found")}

		if passkey_doc.status != "Active":
			return {"success": False, "error": _("Passkey is inactive")}

		public_key_bytes = base64url_to_bytes(passkey_doc.public_key)

		verified_auth = verify_authentication_response(
			credential=credential_response,
			expected_challenge=expected_challenge,
			expected_rp_id=urlparse(frappe.utils.get_url()).hostname,
			expected_origin=frappe.utils.get_url(),
			credential_public_key=public_key_bytes,
			credential_current_sign_count=passkey_doc.sign_count,
			require_user_verification=False,
		)

		# Update sign count
		passkey_doc.sign_count = verified_auth.new_sign_count
		passkey_doc.save(ignore_permissions=True)

		# Login user
		login_manager = LoginManager()
		login_manager.login_as(passkey_doc.user)

		# Clear challenge from cache
		frappe.cache().delete(cache_key)

		return {"success": True, "message": _("Logged in"), "home_page": "/app"}

	except frappe.ValidationError:
		raise
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Passkey Login Verify Failed")
		return {"success": False, "error": _("Authentication failed")}


@frappe.whitelist()
def update_passkey_label(credential_id: str, label: str):
	"""Update passkey label/title"""
	try:
		if not credential_id or not label:
			return {"success": False, "error": _("Credential ID and label are required")}

		# Validate user owns this passkey
		passkey = frappe.get_doc("User Passkey", {"credential_id": credential_id})
		_validate_user_access(passkey.user)

		frappe.db.set_value("User Passkey", {"credential_id": credential_id}, "title", label)
		frappe.db.commit()

		return {"success": True}

	except frappe.DoesNotExistError:
		return {"success": False, "error": _("Passkey not found")}
	except frappe.ValidationError:
		raise
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Update Passkey Label Failed")
		return {"success": False, "error": _("Failed to update passkey label")}


@frappe.whitelist()
def get_active_passkeys(user: str):
	"""Get user's active passkeys"""
	try:
		_validate_user_access(user)

		passkeys = frappe.get_all(
			"User Passkey",
			filters={"user": user, "status": "Active"},
			fields=["name", "creation", "credential_id", "title", "sign_count", "modified as last_used"],
			order_by="creation desc",
		)

		return passkeys

	except frappe.ValidationError:
		raise
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Get Active Passkeys Failed")
		return []


@frappe.whitelist()
def revoke_passkey(name: str):
	"""Revoke a passkey"""
	try:
		if not name:
			return {"success": False, "error": _("Passkey name is required")}

		try:
			doc = frappe.get_doc("User Passkey", name)
		except frappe.DoesNotExistError:
			return {"success": False, "error": _("Passkey not found")}

		_validate_user_access(doc.user)

		doc.status = "Revoked"
		doc.save(ignore_permissions=True)

		return {"success": True}

	except frappe.ValidationError:
		raise
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Revoke Passkey Failed")
		return {"success": False, "error": _("Failed to revoke passkey")}
