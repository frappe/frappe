# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
"""WebAuthn passkey registration and login for User.

A passkey is a credential welded to a single domain, so everything below is keyed on
the host actually serving the request, never on the site name.

Credentials live in the standalone `User Passkey` doctype, which grants `create` and
`write` to nobody. The only writer is this module, using `ignore_permissions`, so a
credential can only come into existence by completing a ceremony.
"""

import json

import frappe
from frappe import _
from frappe.core.doctype.user.user import get_redirect_url_for_user
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, now_datetime, sha256_hash
from frappe.utils.password import get_decrypted_password

CHALLENGE_TTL = 20 * 60


def get_rp_id_and_origin() -> tuple[str, str]:
	import ipaddress
	from urllib.parse import urlsplit

	host = frappe.local.request.host
	rp_id = urlsplit(f"//{host}").hostname

	# the browser exposes WebAuthn only in a secure context, so a ceremony
	# can only ever come from https, or from loopback, which counts as trustworthy too
	name = rp_id.rstrip(".")
	try:
		loopback = ipaddress.ip_address(name).is_loopback
	except ValueError:
		loopback = name == "localhost" or name.endswith(".localhost")

	origin = f"{'http' if loopback else 'https'}://{host}"

	return rp_id, origin


def reject_impersonated_session():
	"""A System Manager must not be able to enroll a credential as someone else."""
	if frappe.session.data.get("impersonated_by"):
		frappe.throw(
			_("Passkeys cannot be enrolled during an impersonated session"),
			frappe.PermissionError,
		)


def stash_challenge(challenge: bytes, ceremony: str, user: str) -> str:
	state = frappe.generate_hash()
	frappe.cache.set_value(
		f"webauthn_challenge:{state}",
		{"challenge": challenge, "ceremony": ceremony, "user": user},
		expires_in_sec=CHALLENGE_TTL,
	)
	return state


def pop_challenge(state: str, ceremony: str, user: str) -> bytes:
	"""Redeem a stashed challenge. Single use - read and delete."""
	cache_key = f"webauthn_challenge:{state}"
	stashed = frappe.cache.get_value(cache_key)
	frappe.cache.delete_value(cache_key)

	if not stashed or stashed.get("ceremony") != ceremony or stashed.get("user") != user:
		frappe.throw(_("This passkey attempt is no longer valid. Please try again."))

	return stashed["challenge"]


def parse_credential(credential: str) -> dict:
	try:
		parsed = json.loads(credential)
	except ValueError:
		parsed = None

	if not isinstance(parsed, dict):
		frappe.throw(_("This passkey could not be verified. Please try again."), frappe.ValidationError)

	return parsed


def known_transports() -> set[str]:
	from webauthn.helpers.structs import AuthenticatorTransport

	return {t.value for t in AuthenticatorTransport}


def transport_hints(stored: str | None) -> list | None:
	from webauthn.helpers.structs import AuthenticatorTransport

	known = known_transports()
	hints = [AuthenticatorTransport(hint) for hint in (stored or "").split(", ") if hint in known]
	return hints or None


def transports_to_store(credential: dict) -> str:
	response = credential.get("response")
	transports = response.get("transports") if isinstance(response, dict) else None
	if not isinstance(transports, list):
		return ""

	known = known_transports()
	return ", ".join(t for t in transports if isinstance(t, str) and t in known)


def validate_enrollment_link(key: str, ignore_expiry: bool = False) -> frappe._dict | None:
	"""Resolve a reset link to the user it may enroll a passkey for, else None."""
	from datetime import timedelta

	if not key:
		return None

	row = frappe.db.get_value(
		"User",
		{"reset_password_key": sha256_hash(key), "enabled": 1},
		[
			"name",
			"full_name",
			"enabled",
			"last_reset_password_key_generated_on",
			"reset_link_from_desk",
		],
		as_dict=True,
	)
	if not row:
		return None

	# only a link requested from an authenticated desk session may enroll a passkey
	if not cint(row.reset_link_from_desk):
		return None

	if ignore_expiry:
		return row

	expiry = cint(frappe.get_system_settings("reset_password_link_expiry_duration"))
	if expiry and row.last_reset_password_key_generated_on:
		if now_datetime() > row.last_reset_password_key_generated_on + timedelta(seconds=expiry):
			return None

	return row


def link_allows_passkey(key: str) -> bool:
	"""Whether the update-password page should offer passkey enrollment for this key."""
	return bool(validate_enrollment_link(key, ignore_expiry=True))


def user_from_enrollment_key(key: str) -> frappe._dict:
	user = validate_enrollment_link(key)
	if not user:
		frappe.throw(
			_("This link is invalid or has expired. Please request a new one."),
			frappe.PermissionError,
		)
	return user


def consume_enrollment_key(key: str):
	frappe.db.set_value(
		"User",
		{"reset_password_key": sha256_hash(key), "enabled": 1},
		{"reset_password_key": "", "reset_link_from_desk": 0},
	)


def enrolling_user(key: str | None) -> frappe._dict:
	"""Who this registration ceremony is for: the session user, or an email link's user."""
	if key:
		return user_from_enrollment_key(key)

	reject_impersonated_session()
	if frappe.session.user in ("Guest", ""):
		raise frappe.PermissionError

	user = frappe.db.get_value(
		"User", {"name": frappe.session.user, "enabled": 1}, ["name", "full_name"], as_dict=True
	)
	if not user:
		raise frappe.PermissionError

	return user


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=20, seconds=60 * 60)
def register_options(key: str | None = None):
	"""Challenge + parameters for `navigator.credentials.create()`."""
	from webauthn import generate_registration_options, options_to_json
	from webauthn.helpers import base64url_to_bytes
	from webauthn.helpers.structs import (
		AuthenticatorSelectionCriteria,
		PublicKeyCredentialDescriptor,
		ResidentKeyRequirement,
		UserVerificationRequirement,
	)

	user = enrolling_user(key)
	rp_id, _origin = get_rp_id_and_origin()

	options = generate_registration_options(
		rp_id=rp_id,
		rp_name=frappe.get_website_settings("app_name") or "Frappe",
		user_id=sha256_hash(user.name).encode(),
		user_name=user.name,
		user_display_name=user.full_name or user.name,
		authenticator_selection=AuthenticatorSelectionCriteria(
			# discoverable, so login needs no email; biometric/PIN always required
			resident_key=ResidentKeyRequirement.REQUIRED,
			user_verification=UserVerificationRequirement.REQUIRED,
		),
		# stops the same authenticator enrolling twice; the transport hints tell the
		# client where to look for it instead of probing every transport
		exclude_credentials=[
			PublicKeyCredentialDescriptor(
				id=base64url_to_bytes(enrolled.credential_id),
				transports=transport_hints(enrolled.transports),
			)
			for enrolled in frappe.get_all(
				"User Passkey",
				filters={"user": user.name},
				fields=["credential_id", "transports"],
			)
		],
	)

	return {
		"state": stash_challenge(options.challenge, "register", user.name),
		"options": json.loads(options_to_json(options)),
	}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=20, seconds=60 * 60)
def register_verify(state: str, credential: str, label: str | None = None, key: str | None = None):
	"""Verify the attestation from `navigator.credentials.create()` and store it."""
	from webauthn import verify_registration_response
	from webauthn.helpers import bytes_to_base64url
	from webauthn.helpers.exceptions import WebAuthnException

	user = enrolling_user(key).name
	rp_id, origin = get_rp_id_and_origin()
	parsed = parse_credential(credential)

	try:
		verified = verify_registration_response(
			credential=credential,
			expected_challenge=pop_challenge(state, "register", user),
			expected_rp_id=rp_id,
			expected_origin=origin,
			require_user_verification=True,
		)
	except WebAuthnException:
		frappe.throw(_("This passkey could not be verified. Please try again."), frappe.ValidationError)

	credential_id = bytes_to_base64url(verified.credential_id)
	if frappe.db.exists("User Passkey", {"credential_id": credential_id}):
		frappe.throw(_("This passkey is already registered"))

	doc = frappe.get_doc(
		{
			"doctype": "User Passkey",
			"user": user,
			"label": label or _("Passkey"),
			"rp_id": rp_id,
			"credential_id": credential_id,
			"public_key": bytes_to_base64url(verified.credential_public_key),
			"sign_count": verified.sign_count,
			"multi_device": cint(verified.credential_device_type.value == "multi_device"),
			"backed_up": cint(verified.credential_backed_up),
			"transports": transports_to_store(parsed),
		}
	)
	doc.insert(ignore_permissions=True)

	notify_passkey_enrolled(user, doc.label)

	if key:
		consume_enrollment_key(key)

		# enrollment from an email link runs as Guest, so the user is logged in here to start a session
		frappe.local.login_manager.login_as(user)

		row = frappe.db.get_value("User", user, ["user_type", "redirect_url"], as_dict=True)
		return {"redirect_to": get_redirect_url_for_user(row.redirect_url, row.user_type)}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=60, seconds=60 * 60)
def login_options():
	"""Challenge + parameters for `navigator.credentials.get()`."""
	from webauthn import generate_authentication_options, options_to_json
	from webauthn.helpers.structs import UserVerificationRequirement

	rp_id, _origin = get_rp_id_and_origin()

	options = generate_authentication_options(
		rp_id=rp_id,
		user_verification=UserVerificationRequirement.REQUIRED,
	)

	return {
		"state": stash_challenge(options.challenge, "login", "Guest"),
		"options": json.loads(options_to_json(options)),
	}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=60, seconds=60 * 60)
def login(state: str, credential: str):
	"""Verify the assertion from `navigator.credentials.get()` and start a session."""
	from webauthn import verify_authentication_response
	from webauthn.helpers import base64url_to_bytes
	from webauthn.helpers.exceptions import WebAuthnException

	login_manager = frappe.local.login_manager
	login_manager.run_trigger("before_login")
	expected_challenge = pop_challenge(state, "login", "Guest")
	rp_id, origin = get_rp_id_and_origin()

	credential_id = parse_credential(credential).get("id")
	passkey = (
		frappe.db.get_value(
			"User Passkey",
			{"credential_id": credential_id},
			["name", "user", "sign_count"],
			as_dict=True,
		)
		if isinstance(credential_id, str)
		else None
	)
	if not passkey:
		login_manager.fail(_("Unknown passkey"))

	if not (frappe.db.get_value("User", passkey.user, "enabled") or passkey.user == "Administrator"):
		login_manager.fail(_("User disabled or missing"), user=passkey.user)

	try:
		public_key = get_decrypted_password("User Passkey", passkey.name, "public_key")
	except frappe.ValidationError:
		frappe.clear_last_message()
		frappe.log_error("Unable to decrypt passkey public key")
		login_manager.fail(_("This passkey could not be verified."), user=passkey.user)

	try:
		verified = verify_authentication_response(
			credential=credential,
			expected_challenge=expected_challenge,
			expected_rp_id=rp_id,
			expected_origin=origin,
			credential_public_key=base64url_to_bytes(public_key),
			credential_current_sign_count=passkey.sign_count,
			require_user_verification=True,
		)
	except WebAuthnException:
		login_manager.fail(_("This passkey could not be verified."), user=passkey.user)

	frappe.db.set_value(
		"User Passkey",
		passkey.name,
		{
			"sign_count": verified.new_sign_count,
			"last_used": now_datetime(),
			"multi_device": cint(verified.credential_device_type.value == "multi_device"),
			"backed_up": cint(verified.credential_backed_up),
		},
		update_modified=False,
	)

	# a passkey already proves possession plus user verification, so no second factor is needed
	login_manager.login_as(passkey.user)


def check_passkey_access(user: str | None):
	if user != frappe.session.user and "System Manager" not in frappe.get_roles():
		frappe.throw(_("Not permitted"), frappe.PermissionError)


@frappe.whitelist(methods=["POST"])
def remove_passkey(name: str):
	"""Remove a passkey from a user. User must be the owner or a System Manager."""
	check_passkey_access(frappe.db.get_value("User Passkey", name, "user"))
	frappe.delete_doc("User Passkey", name, ignore_permissions=True)


@frappe.whitelist(methods=["POST"])
def rename_passkey(name: str, label: str):
	"""Rename a passkey. Only the user it belongs to may rename it."""
	doc = frappe.get_doc("User Passkey", name)
	if doc.user != frappe.session.user:
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	# saved through the doc so the label meets the same rules a new one does: mandatory,
	# within the column, and stripped of html
	doc.label = label
	doc.save(ignore_permissions=True)


@frappe.whitelist()
def get_passkeys(user: str):
	"""Get all passkeys for a user. Must be the owner or a System Manager."""
	check_passkey_access(user)
	return frappe.get_all(
		"User Passkey",
		filters={"user": user},
		fields=["name", "label", "rp_id", "last_used", "multi_device", "backed_up"],
		order_by="creation desc",
	)


def notify_passkey_enrolled(user: str, label: str):
	"""Alert the user that a new passkey was registered on their account."""
	try:
		frappe.get_doc(
			{
				"doctype": "Activity Log",
				"user": user,
				"status": "Success",
				"subject": _("Passkey {0} enrolled").format(label),
				"operation": "Login",
			}
		).insert(ignore_permissions=True, ignore_links=True)

		frappe.sendmail(
			recipients=[frappe.db.get_value("User", user, "email")],
			subject=_("Security Alert: A passkey was added to your account"),
			content=_(
				"A new passkey named <b>{0}</b> was just added to your account.<br><br>"
				"If this was not you, remove it from your User page and contact your "
				"System Manager immediately."
			).format(frappe.utils.escape_html(label)),
		)
	except Exception:
		# the passkey row is already inserted: failing here would roll it back while the
		# passkey stays on the user's authenticator
		frappe.clear_last_message()
		frappe.log_error("Unable to send passkey enrollment notification")
