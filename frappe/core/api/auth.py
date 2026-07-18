# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Public auth API — login/logout, passwords, sign up, API keys and sessions.

Endpoints were consolidated from `frappe.handler`, `frappe.www.login`,
`frappe.auth`, `frappe.twofactor`, `frappe.sessions` and the User doctype
module; the old dotted paths keep working via aliases in the original
modules. Handle with care: everything here is security-sensitive.
"""

from typing import TYPE_CHECKING

import frappe
from frappe import _
from frappe.apps import get_default_path
from frappe.auth import MAX_PASSWORD_SIZE, LoginManager
from frappe.public_api import public
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, escape_html, today
from frappe.utils.data import sha256_hash
from frappe.utils.password import get_password_reset_limit, is_password_reused
from frappe.utils.password import update_password as _update_password
from frappe.website.utils import get_home_page, is_signup_disabled
from frappe.www.login import get_login_with_email_link_ratelimit

if TYPE_CHECKING:
	from frappe.core.doctype.user.user import User

# ---------------------------------------------------------------------------
# Login and logout
# ---------------------------------------------------------------------------


@public(group="Auth")
@frappe.whitelist(allow_guest=True, methods=["POST"])
def logout() -> None:
	"""Log out the current session."""
	frappe.local.login_manager.logout()
	frappe.db.commit()


@public(group="Auth")
@frappe.whitelist(allow_guest=True, methods=["POST"])
def web_logout() -> None:
	"""Log out the current session and respond with a "logged out" web page."""
	frappe.local.login_manager.logout()
	frappe.db.commit()
	frappe.respond_as_web_page(
		_("Logged Out"), _("You have been successfully logged out"), indicator_color="green"
	)


@public(group="Auth")
@frappe.whitelist(allow_guest=True)
def login_via_token(login_token: str) -> None:
	"""Log in using a one-time login token and redirect to the app or website.

	:param login_token: one-time login token that maps to a session
	"""
	from frappe.utils.oauth import redirect_post_login

	sid = frappe.cache.get_value(f"login_token:{login_token}", expires=True)
	if not sid:
		frappe.respond_as_web_page(_("Invalid Request"), _("Invalid Login Token"), http_status_code=417)
		return

	frappe.local.form_dict.sid = sid
	frappe.local.login_manager = LoginManager()

	redirect_post_login(
		desk_user=frappe.db.get_value("User", frappe.session.user, "user_type") == "System User"
	)


@public(group="Auth")
@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=get_login_with_email_link_ratelimit, seconds=60 * 60)
def send_login_link(email: str) -> None:
	"""Email a one-time login link, if login with email link is enabled.

	Responds identically whether or not the email belongs to a user, to
	prevent user enumeration.

	:param email: email address of the user
	"""
	from frappe.www.login import _generate_temporary_login_link

	if not frappe.get_system_settings("login_with_email_link"):
		return

	try:
		expiry = frappe.get_system_settings("login_with_email_link_expiry") or 10
		link = _generate_temporary_login_link(email, expiry)

		app_name = (
			frappe.get_website_settings("app_name") or frappe.get_system_settings("app_name") or _("Frappe")
		)

		subject = _("Login To {0}").format(app_name)

		frappe.sendmail(
			subject=subject,
			recipients=email,
			template="login_with_email_link",
			args={"link": link, "minutes": expiry, "app_name": app_name},
			now=True,
		)
	except frappe.DoesNotExistError:
		frappe.clear_messages()
	except frappe.OutgoingEmailError:
		frappe.clear_messages()
		frappe.log_error(title="Login link email could not be sent", message=frappe.get_traceback())
	except Exception:
		frappe.clear_messages()
		frappe.log_error(title="Login link generation failed unexpectedly", message=frappe.get_traceback())


@public(group="Auth")
@frappe.whitelist(allow_guest=True, methods=["GET"])
@rate_limit(limit=get_login_with_email_link_ratelimit, seconds=60 * 60)
def login_via_key(key: str) -> None:
	"""Log in using a one-time login key from a login link email.

	:param key: the one-time login key
	"""
	from frappe.utils.oauth import redirect_post_login

	cache_key = f"one_time_login_key:{key}"
	email = frappe.cache.get_value(cache_key)

	if email:
		frappe.cache.delete_value(cache_key)
		frappe.local.login_manager.login_as(email)

		redirect_post_login(
			desk_user=frappe.db.get_value("User", frappe.session.user, "user_type") == "System User"
		)
	else:
		frappe.respond_as_web_page(
			_("Not Permitted"),
			_("The link you trying to login is invalid or expired."),
			http_status_code=403,
			indicator_color="red",
		)


@public(group="Auth")
@frappe.whitelist()
def get_logged_user() -> str:
	"""Return the user of the current session.

	:return: The session user's name (email).
	"""
	return frappe.session.user


@public(group="Auth")
@frappe.whitelist()
def reset_otp_secret(user: str) -> None:
	"""Reset a user's two factor auth OTP secret and notify them by email.

	Users can reset their own secret; resetting another user's secret
	requires the System Manager role.

	:param user: the user whose OTP secret is reset
	"""
	from frappe.defaults import clear_default
	from frappe.utils.background_jobs import enqueue

	if frappe.session.user != user:
		frappe.only_for("System Manager", message=True)

	settings = frappe.get_cached_doc("System Settings")

	if not settings.enable_two_factor_auth:
		frappe.throw(
			_("You have to enable Two Factor Auth from System Settings."),
			title=_("Enable Two Factor Auth"),
		)

	otp_issuer = settings.otp_issuer_name or "Frappe Framework"
	user_email = frappe.get_cached_value("User", user, "email")

	clear_default(user + "_otplogin")
	clear_default(user + "_otpsecret")

	email_args = {
		"recipients": user_email,
		"sender": None,
		"subject": _("OTP Secret Reset - {0}").format(otp_issuer),
		"message": _(
			"<p>Your OTP secret on {0} has been reset. If you did not perform this reset and did not request it, please contact your System Administrator immediately.</p>"
		).format(otp_issuer),
		"delayed": False,
		"retry": 3,
	}

	enqueue(
		method=frappe.sendmail,
		queue="short",
		timeout=300,
		event=None,
		is_async=True,
		job_name=None,
		now=False,
		**email_args,
	)

	frappe.msgprint(_("OTP Secret has been reset. Re-registration will be required on next login."))


@public(group="Auth")
@frappe.whitelist()
def clear_cache() -> None:
	"""Clear the server-side cache of the current user."""
	from frappe.cache_manager import clear_user_cache

	# updating session causes a commit, explicit commit not needed
	frappe.local.session_obj.update(force=True)
	clear_user_cache(frappe.session.user)
	frappe.response["message"] = _("Cache Cleared")


@public(group="Auth")
@frappe.whitelist(allow_guest=True, methods=["POST"])
def update_password(
	new_password: str, logout_all_sessions: int = 0, key: str | None = None, old_password: str | None = None
) -> str:
	"""Update the password of the current user (or of a password-reset key's user).

	:param new_password: the new password
	:param logout_all_sessions: log out all other sessions if set to 1
	:param key: password reset key, when resetting a forgotten password
	:param old_password: current password, when changing a known password
	:return: The path to redirect to after login with the new password.
	"""
	from frappe.core.doctype.user.user import (
		_get_user_for_update_password,
		handle_password_test_fail,
		reset_user_data,
	)

	if len(new_password) > MAX_PASSWORD_SIZE:
		frappe.throw(_("Password size exceeded the maximum allowed size."))

	result = test_password_strength(new_password)
	feedback = result.get("feedback", None)

	if feedback and not feedback.get("password_policy_validation_passed", False):
		handle_password_test_fail(feedback)

	res = _get_user_for_update_password(key, old_password)
	if res.get("message"):
		frappe.local.response.http_status_code = 410
		return res["message"]
	else:
		user = res["user"]

	if is_password_reused(user, new_password):
		frappe.throw(
			_(
				"New password cannot be the same as your current password. Please choose a different password."
			),
			title=_("Invalid Password"),
		)

	logout_all_sessions = cint(logout_all_sessions) or frappe.get_system_settings("logout_on_password_reset")
	_update_password(user, new_password, logout_all_sessions=cint(logout_all_sessions))

	user_doc, redirect_url = reset_user_data(user)

	user_doc.validate_reset_password()

	# get redirect url from cache
	redirect_to = frappe.cache.hget("redirect_after_login", user)
	if redirect_to:
		redirect_url = redirect_to
		frappe.cache.hdel("redirect_after_login", user)

	frappe.local.login_manager.login_as(user)

	frappe.db.set_value("User", user, "last_password_reset_date", today())
	frappe.db.set_value("User", user, "reset_password_key", "")

	if user_doc.user_type == "System User":
		return get_default_path() or "/desk"
	else:
		return redirect_url or get_default_path() or get_home_page()


@public(group="Auth")
@frappe.whitelist(allow_guest=True)
def test_password_strength(
	new_password: str, key: str | None = None, old_password: str | None = None, user_data: tuple | None = None
) -> dict | None:
	"""Score a password against the site's password policy.

	:param new_password: the password to be tested
	:param key: deprecated, unused
	:param old_password: deprecated, unused
	:param user_data: user attributes the password must not resemble
	:return: Dict with `score` and `feedback`, or empty when the policy is disabled.
	"""
	from frappe.utils.password_strength import test_password_strength as _test_password_strength

	if key is not None or old_password is not None:
		from frappe.deprecation_dumpster import deprecation_warning

		deprecation_warning(
			"unknown",
			"v17",
			"Arguments `key` and `old_password` are deprecated in function `test_password_strength`.",
		)

	enable_password_policy = frappe.get_system_settings("enable_password_policy")

	if not enable_password_policy:
		return {}

	if not user_data:
		user_data = frappe.db.get_value(
			"User", frappe.session.user, ["first_name", "middle_name", "last_name", "email", "birth_date"]
		)

	if new_password:
		result = _test_password_strength(new_password, user_inputs=user_data)
		password_policy_validation_passed = False
		minimum_password_score = cint(frappe.get_system_settings("minimum_password_score"))

		# score should be greater than 0 and minimum_password_score
		if result.get("score") and result.get("score") >= minimum_password_score:
			password_policy_validation_passed = True

		result["feedback"]["password_policy_validation_passed"] = password_policy_validation_passed
		return {"score": result["score"], "feedback": result["feedback"]}


@public(group="Auth")
@frappe.whitelist(methods=["POST"])
def verify_password(password: str) -> None:
	"""Verify the current user's password, throwing if it does not match.

	:param password: the password to be verified
	"""
	frappe.local.login_manager.check_password(frappe.session.user, password)


@public(group="Auth")
@frappe.whitelist(allow_guest=True)
def sign_up(email: str, full_name: str, redirect_to: str) -> tuple[int, str]:
	"""Sign up a new website user.

	:param email: email address of the new user
	:param full_name: full name of the new user
	:param redirect_to: path to redirect to after the first login
	:return: Status code (0 already registered, 1 mail sent, 2 needs verification) and message.
	"""
	from frappe.www.login import sanitize_redirect

	if is_signup_disabled():
		frappe.throw(_("Sign Up is disabled"), title=_("Not Allowed"))

	user = frappe.db.get("User", {"email": email})
	if user:
		if user.enabled:
			return 0, _("Already Registered")
		else:
			return 0, _("Registered but disabled")
	else:
		max_signups_allowed_per_hour = cint(frappe.get_system_settings("max_signups_allowed_per_hour") or 300)
		users_created_past_hour = frappe.db.get_creation_count("User", 60)
		if users_created_past_hour >= max_signups_allowed_per_hour:
			frappe.respond_as_web_page(
				_("Temporarily Disabled"),
				_(
					"Too many users signed up recently, so the registration is disabled. Please try back in an hour"
				),
				http_status_code=429,
			)

		from frappe.utils import random_string

		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": escape_html(full_name),
				"enabled": 1,
				"new_password": random_string(10),
				"user_type": "Website User",
			}
		)
		user.flags.ignore_permissions = True
		user.flags.ignore_password_policy = True
		user.insert()

		# set default signup role as per Portal Settings
		default_role = frappe.get_single_value("Portal Settings", "default_role")
		if default_role:
			user.add_roles(default_role)

		if redirect_to:
			frappe.cache.hset("redirect_after_login", user.name, sanitize_redirect(redirect_to))

		if user.flags.email_sent:
			return 1, _("Please check your email for verification")
		else:
			return 2, _("Please ask your administrator to verify your sign-up")


@public(group="Auth")
@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=get_password_reset_limit, seconds=60 * 60)
def reset_password(user: str) -> None:
	"""Send password reset instructions to a user's email.

	Responds identically whether or not the user exists or is enabled, to
	prevent username enumeration (CWE-204).

	:param user: name (email) of the user
	"""
	# Always return the same generic response regardless of whether the user
	# exists, is disabled, or is restricted. This prevents username enumeration
	# via different messages or HTTP status codes (CWE-204).

	try:
		user_doc: User = frappe.get_doc("User", user)
		if user_doc.name != "Administrator" and user_doc.enabled:
			user_doc.validate_reset_password()
			user_doc._reset_password(send_email=True)
		# For Administrator or disabled users: silently skip — same response below
	except frappe.DoesNotExistError:
		frappe.clear_messages()
	except frappe.OutgoingEmailError:
		frappe.clear_messages()
		frappe.log_error(title="Password reset email could not be sent", message=frappe.get_traceback())
	except Exception:
		frappe.clear_messages()
		frappe.log_error(title="Password reset failed unexpectedly", message=frappe.get_traceback())

	frappe.msgprint(
		msg=_(
			"If this email is registered with us, we have sent password reset instructions to it. Please check your inbox."
		),
		title=_("Password Reset"),
	)


@public(group="Auth")
@frappe.whitelist(methods=["POST"])
def change_password(user: str, new_password: str, logout_all_sessions: int = 1) -> None:
	"""Change a user's password; requires write permission on the user.

	:param user: name of the user
	:param new_password: the new password
	:param logout_all_sessions: log out all of the user's sessions if set to 1
	"""
	user_doc: User = frappe.get_doc("User", user)
	user_doc.check_permission("write")
	user_doc.new_password = new_password
	user_doc.logout_all_sessions = logout_all_sessions
	user_doc.save()


@public(group="Auth")
@frappe.whitelist(methods=["POST"])
def generate_api_keys(user: str) -> dict[str, str]:
	"""Generate an API secret (and API key, if unset) for a user.

	:param user: name of the user
	:return: Dict with the user's `api_key` and the new `api_secret`.
	"""
	frappe.only_for("System Manager")
	user_details: User = frappe.get_doc("User", user)
	api_secret = frappe.generate_hash(length=15)
	# if api key is not set generate api key
	if not user_details.api_key:
		api_key = frappe.generate_hash(length=15)
		user_details.api_key = api_key
	user_details.api_secret = api_secret
	user_details.save()

	return {"api_key": user_details.api_key, "api_secret": api_secret}


@public(group="Auth")
@frappe.whitelist(methods=["POST"])
def impersonate(user: str, reason: str) -> None:
	"""Start an impersonation session as another user, notifying them.

	:param user: the user to impersonate
	:param reason: reason for the impersonation, shared with the user
	"""
	frappe.has_permission("User", "impersonate", throw=True)

	impersonator = frappe.session.user
	frappe.get_doc(
		{
			"doctype": "Activity Log",
			"user": user,
			"status": "Success",
			"subject": _("User {0} impersonated as {1}").format(impersonator, user),
			"operation": "Impersonate",
		}
	).insert(ignore_permissions=True, ignore_links=True)

	notification = frappe.new_doc(
		"Notification Log",
		for_user=user,
		from_user=frappe.session.user,
		subject=_("{0} just impersonated as you. They gave this reason: {1}").format(impersonator, reason),
	)
	notification.set("type", "Alert")
	notification.insert(ignore_permissions=True)
	# notify user via email too
	outgoing_email_exists = frappe.db.exists("Email Account", {"default_outgoing": 1, "awaiting_password": 0})
	if outgoing_email_exists:
		user_email = frappe.db.get_value("User", user, "email")
		email_message = _(
			"User {0} has started an impersonation session as you. <br><br><b>Reason provided:</b> {1}"
		).format(escape_html(impersonator), escape_html(reason))

		frappe.sendmail(
			recipients=[user_email],
			subject=_("Security Alert: Your account is being impersonated"),
			content=email_message,
		)
	frappe.local.login_manager.impersonate(user)


@public(group="Auth")
@frappe.whitelist()
@rate_limit(limit=10, seconds=60 * 60, methods="POST")
def clear_session(sid_hash: str) -> None:
	"""Force-log-out one of the current user's own sessions.

	:param sid_hash: sha256 hash of the session id to be terminated
	"""
	from frappe.sessions import delete_session

	sessions = frappe.qb.DocType("Sessions")
	sessions_data = (
		frappe.qb.from_(sessions).select(sessions.sid).where(sessions.user == frappe.session.user)
	).run(pluck=True)

	for session in sessions_data:
		if sha256_hash(session) == sid_hash:
			delete_session(sid=session, reason="Force Logged out by the user", user=frappe.session.user)
			frappe.toast(_("Successfully signed out"))
			return
