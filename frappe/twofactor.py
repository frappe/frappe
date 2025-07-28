# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import os
from base64 import b32encode, b64encode
from io import BytesIO

import pyotp
import frappe
import frappe.defaults
from frappe import _
from frappe.permissions import ALL_USER_ROLE
from frappe.utils import cint, get_datetime, get_url, time_diff_in_seconds
from frappe.utils.background_jobs import enqueue
from frappe.utils.password import decrypt, encrypt

PARENT_FOR_DEFAULTS = "__2fa"


# ---------------------------------------------------------------------------
# Default Value Management for OTP
# ---------------------------------------------------------------------------

def get_default(key: str) -> str | None:
	"""Fetch default value for a key under 2FA defaults."""
	return frappe.db.get_default(key, parent=PARENT_FOR_DEFAULTS)


def set_default(key: str, value: str) -> None:
	"""Set a default value for a key under 2FA defaults."""
	frappe.db.set_default(key, value, parent=PARENT_FOR_DEFAULTS)


def clear_default(key: str) -> None:
	"""Clear a default value for a key under 2FA defaults."""
	frappe.defaults.clear_default(key, parent=PARENT_FOR_DEFAULTS)


# ---------------------------------------------------------------------------
# 2FA Core
# ---------------------------------------------------------------------------

class ExpiredLoginException(Exception):
	pass


def toggle_two_factor_auth(state: bool, roles: list[str] | None = None) -> None:
	"""Enable or disable 2FA for given roles."""
	for role in roles or []:
		role_doc = frappe.get_doc("Role", {"role_name": role})
		role_doc.two_factor_auth = cint(state)
		role_doc.save(ignore_permissions=True)


def two_factor_is_enabled(user: str | None = None) -> bool:
	"""Check if 2FA is enabled globally or for a specific user."""
	enabled = cint(frappe.get_system_settings("enable_two_factor_auth"))

	if enabled and user:
		bypass_2fa = cint(frappe.get_system_settings("bypass_2fa_for_retricted_ip_users"))
		if bypass_2fa:
			user_doc = frappe.get_doc("User", user)
			restricted_ips = user_doc.get_restricted_ip_list() or []
			if frappe.local.request_ip and any(frappe.local.request_ip.startswith(ip) for ip in restricted_ips):
				return False

	return enabled if not user else two_factor_is_enabled_for_(user)


def should_run_2fa(user: str) -> bool:
	"""Return True if 2FA checks must be applied for a user."""
	return two_factor_is_enabled(user=user)


def get_cached_user_pass() -> tuple[str | None, str | None]:
	"""Retrieve cached username and password for temporary login sessions."""
	tmp_id = frappe.form_dict.get("tmp_id")
	if tmp_id:
		user = frappe.safe_decode(frappe.cache.get(f"{tmp_id}_usr"))
		pwd = frappe.safe_decode(frappe.cache.get(f"{tmp_id}_pwd"))
		return user, pwd
	return None, None


def authenticate_for_2factor(user: str) -> None:
	"""Handle OTP authentication for 2FA-enabled users before login."""
	if frappe.form_dict.get("otp"):
		return

	otp_secret = get_otpsecret_for_(user)
	token = int(pyotp.TOTP(otp_secret).now())
	tmp_id = frappe.generate_hash(length=8)

	cache_2fa_data(user, token, otp_secret, tmp_id)

	frappe.local.response["verification"] = get_verification_obj(user, token, otp_secret)
	frappe.local.response["tmp_id"] = tmp_id


def cache_2fa_data(user: str, token: int, otp_secret: str, tmp_id: str) -> None:
	"""Cache OTP and credentials with expiry."""
	pwd = frappe.form_dict.get("pwd")
	verification_method = get_verification_method()

	expiry_time = frappe.flags.token_expiry or 300 if verification_method in ["SMS", "Email"] else frappe.flags.otp_expiry or 180

	pipeline = frappe.cache.pipeline()
	pipeline.set(f"{tmp_id}_token", token, expiry_time)
	for k, v in {"_usr": user, "_pwd": pwd, "_otp_secret": otp_secret}.items():
		pipeline.set(f"{tmp_id}{k}", v, expiry_time)
	pipeline.execute()


def two_factor_is_enabled_for_(user: str) -> bool:
	"""Check if 2FA is enabled for a specific user."""
	if user == "Administrator":
		return False

	user_doc = frappe.get_doc("User", user) if isinstance(user, str) else user
	roles = [d.role for d in user_doc.roles or []] + [ALL_USER_ROLE]

	role_doctype = frappe.qb.DocType("Role")
	return frappe.db.count(role_doctype, filters=((role_doctype.two_factor_auth == 1) & (role_doctype.name.isin(roles)))) > 0


def get_otpsecret_for_(user: str) -> str:
	"""Generate or retrieve OTP secret for a user."""
	if (otp_secret := get_default(f"{user}_otpsecret")):
		return decrypt(otp_secret, key=f"{user}.otpsecret")

	otp_secret = b32encode(os.urandom(10)).decode("utf-8")
	set_default(f"{user}_otpsecret", encrypt(otp_secret))
	frappe.db.commit()
	return otp_secret


def get_verification_method() -> str:
	"""Fetch current 2FA method (Email, SMS, OTP App)."""
	return frappe.get_system_settings("two_factor_method")


# ---------------------------------------------------------------------------
# OTP Confirmation
# ---------------------------------------------------------------------------

def confirm_otp_token(login_manager, otp=None, tmp_id=None) -> bool:
	"""Validate OTP token for user login."""
	from frappe.auth import get_login_attempt_tracker

	otp = otp or frappe.form_dict.get("otp")
	if not otp:
		return not two_factor_is_enabled_for_(login_manager.user)

	tmp_id = tmp_id or frappe.form_dict.get("tmp_id")
	hotp_token = frappe.cache.get(f"{tmp_id}_token")
	otp_secret = frappe.cache.get(f"{tmp_id}_otp_secret")

	if not otp_secret:
		raise ExpiredLoginException(_("Login session expired, refresh page to retry"))

	tracker = get_login_attempt_tracker(login_manager.user)
	hotp = pyotp.HOTP(otp_secret)

	if hotp_token and hotp.verify(otp, int(hotp_token)):
		frappe.cache.delete(f"{tmp_id}_token")
		tracker.add_success_attempt()
		return True

	tracker.add_failure_attempt()
	login_manager.fail(_("Incorrect Verification code"), login_manager.user)

	totp = pyotp.TOTP(otp_secret)
	if totp.verify(otp):
		if not get_default(f"{login_manager.user}_otplogin"):
			set_default(f"{login_manager.user}_otplogin", 1)
			delete_qrimage(login_manager.user)
		tracker.add_success_attempt()
		return True

	tracker.add_failure_attempt()
	login_manager.fail(_("Incorrect Verification code"), login_manager.user)
	return False


# ---------------------------------------------------------------------------
# QR, SMS, Email 2FA
# ---------------------------------------------------------------------------

def get_verification_obj(user: str, token: int, otp_secret: str) -> dict:
	"""Generate verification object based on configured 2FA method."""
	otp_issuer = frappe.get_system_settings("otp_issuer_name")
	method = get_verification_method()

	if method == "SMS":
		return process_2fa_for_sms(user, token, otp_secret)
	elif method == "OTP App":
		return (
			process_2fa_for_email(user, token, otp_secret, otp_issuer, method="OTP App")
			if not get_default(f"{user}_otplogin")
			else process_2fa_for_otp_app(user, otp_secret, otp_issuer)
		)
	elif method == "Email":
		return process_2fa_for_email(user, token, otp_secret, otp_issuer)

	return {}


def process_2fa_for_sms(user: str, token: int, otp_secret: str) -> dict:
	"""Send OTP via SMS."""
	phone = frappe.db.get_value("User", user, ["phone", "mobile_no"], as_dict=True)
	phone_number = phone.mobile_no or phone.phone
	status = send_token_via_sms(otp_secret, token=token, phone_no=phone_number)
	return {
		"token_delivery": status,
		"prompt": status and _("Enter verification code sent to {}").format(phone_number[:4] + "******" + phone_number[-3:]),
		"method": "SMS",
		"setup": status,
	}


def process_2fa_for_otp_app(user: str, otp_secret: str, otp_issuer: str) -> dict:
	"""Prepare OTP App setup prompt."""
	return {"method": "OTP App", "setup": bool(get_default(f"{user}_otplogin"))}


def process_2fa_for_email(user: str, token: int, otp_secret: str, otp_issuer: str, method="Email") -> dict:
	"""Send OTP via email."""
	if method == "OTP App" and not get_default(f"{user}_otplogin"):
		totp_uri = pyotp.TOTP(otp_secret).provisioning_uri(user, issuer_name=otp_issuer)
		qrcode_link = get_link_for_qrcode(user, totp_uri)
		message = get_email_body_for_qr_code({"qrcode_link": qrcode_link})
		subject = get_email_subject_for_qr_code({"qrcode_link": qrcode_link})
		prompt = _("Please check your email for setup instructions.")
	else:
		subject = None
		message = None
		prompt = _("Verification code has been sent to your registered email address.")

	status = send_token_via_email(user, token, otp_secret, otp_issuer, subject=subject, message=message)
	return {"token_delivery": status, "prompt": prompt, "method": "Email", "setup": status}


# ---------------------------------------------------------------------------
# Reset OTP Secret
# ---------------------------------------------------------------------------

@frappe.whitelist()
def reset_otp_secret(user: str):
	"""Reset OTP secret for a user."""
	if frappe.session.user != user:
		frappe.only_for("System Manager", message=True)

	settings = frappe.get_cached_doc("System Settings")
	if not settings.enable_two_factor_auth:
		frappe.throw(_("You must enable Two Factor Auth from System Settings."), title=_("Enable Two Factor Auth"))

	otp_issuer = settings.otp_issuer_name or "Frappe Framework"
	user_email = frappe.get_cached_value("User", user, "email")

	clear_default(f"{user}_otplogin")
	clear_default(f"{user}_otpsecret")

	email_args = {
		"recipients": user_email,
		"subject": _("OTP Secret Reset - {0}").format(otp_issuer),
		"message": _(
			"<p>Your OTP secret on {0} has been reset. If this wasn't done by you, contact your Administrator immediately.</p>"
		).format(otp_issuer),
		"delayed": False,
		"retry": 3,
	}

	enqueue(method=frappe.sendmail, queue="short", timeout=300, **email_args)
	frappe.msgprint(_("OTP Secret has been reset. Re-registration will be required on next login."))
