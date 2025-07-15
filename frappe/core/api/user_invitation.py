import frappe
from frappe import _
from frappe.model.document import Document


def _validate_app_name(app_name: str) -> None:
	if app_name not in frappe.get_installed_apps():
		frappe.throw(_("Application is not installed"))


def _get_allowed_roles(app_name: str) -> list[str]:
	user_invitation_hook = frappe.get_hooks("user_invitation", app_name=app_name)
	allowed_roles = user_invitation_hook.get("allowed_invite_roles")
	return allowed_roles if allowed_roles is not None else []


def _validate_role(role: str, allowed_roles: list[str]) -> None:
	if role not in allowed_roles:
		frappe.throw(_("Role is not in the allowed roles list"))


def _validate_emails(emails: str) -> list[str]:
	frappe.utils.validate_email_address(emails, throw=True)
	email_list = frappe.utils.split_emails(emails)
	if not email_list:
		frappe.throw(_("No email addresses found"))
	return email_list


def _get_existing_user_emails(email_list: list[str]) -> list[str]:
	return frappe.db.get_all("User", filters={"email": ["in", email_list]}, pluck="email")


def _get_existing_invited_emails(email_list: list[str], allowed_roles: list[str] | None) -> list[str]:
	filters = {"email": ["in", email_list], "status": "Pending"}
	if allowed_roles is not None:
		filters["role"] = ["in", allowed_roles]
	return frappe.db.get_all("User Invitation", filters=filters, pluck="email")


@frappe.whitelist()
def invite_by_email(
	emails: str, role: str, redirect_to_path: str, app_name: str | None = None
) -> dict[str, list[str]]:
	frappe.only_for(["System Manager", "User Invitation Manager"])
	app_name = app_name if app_name is not None else "frappe"
	_validate_app_name(app_name)
	allowed_roles: list[str] = []
	if app_name != "frappe":
		allowed_roles = _get_allowed_roles(app_name)
		_validate_role(role, allowed_roles)
	email_list = _validate_emails(emails)
	existing_user_emails = _get_existing_user_emails(email_list)
	existing_invited_emails = _get_existing_invited_emails(
		email_list, allowed_roles if app_name != "frappe" else None
	)
	to_invite = list(set(email_list) - set(existing_user_emails) - set(existing_invited_emails))
	for email in to_invite:
		invitation = frappe.new_doc("User Invitation")
		invitation.email = email
		invitation.role = role
		invitation.app_name = app_name
		invitation.redirect_to_path = redirect_to_path
		invitation.insert()
	return {
		"existing_user_emails": existing_user_emails,
		"existing_invited_emails": existing_invited_emails,
		"invited_emails": to_invite,
	}


def _get_invitation(key: str) -> Document:
	result = frappe.db.get_all("User Invitation", filters={"key": key}, pluck="name")
	if not result:
		frappe.throw(_("Invalid key"))
	return frappe.get_doc("User Invitation", result[0])


def _upsert_user(email: str, role: str) -> Document:
	user: Document | None = None
	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
	else:
		user = frappe.new_doc("User")
		user.user_type = "System User"
		user.email = email
		user.first_name = email.split("@")[0].title()
		user.send_welcome_email = False
		user.insert()
	user.append_roles(role)
	user.save(ignore_permissions=True)
	return user


def _accept_invitation(invitation: Document, user_email: str) -> None:
	invitation.status = "Accepted"
	invitation.accepted_at = frappe.utils.now()
	invitation.user = user_email
	invitation.save(ignore_permissions=True)


def _run_after_invite_accept_fns(invitation: Document) -> None:
	after_accept_fns = []
	user_invitation_hook = frappe.get_hooks("user_invitation", app_name=invitation.app_name)
	after_accept = user_invitation_hook.get("after_accept")
	after_accept = after_accept if after_accept is not None else []
	for dot_path in after_accept:
		after_accept_fns.append(frappe.get_attr(dot_path))
	for after_accept_fn in after_accept_fns:
		after_accept_fn(invitation)


def _should_user_update_password(user: Document) -> bool:
	return not user.last_password_reset_date and not bool(
		frappe.get_system_settings("disable_user_pass_login")
	)


def _set_reset_password_key(user: Document) -> str:
	key = frappe.generate_hash()
	hashed_key = frappe.utils.sha256_hash(key)
	user.reset_password_key = hashed_key
	user.last_reset_password_key_generated_on = frappe.utils.now_datetime()
	user.save(ignore_permissions=True)
	return key


@frappe.whitelist(allow_guest=True)
def accept_invitation(key: str) -> None:
	invitation = _get_invitation(key)
	if invitation.status == "Expired":
		frappe.throw(_("Invitation is expired"))
	if invitation.status == "Pending":
		user = _upsert_user(invitation.email, invitation.role)
		_accept_invitation(invitation, user.email)
		if invitation.app_name != "frappe":
			_run_after_invite_accept_fns(invitation)
	user = frappe.get_doc("User", invitation.email)
	redirect_to = invitation.get_redirect_to_path()
	should_update_password = _should_user_update_password(user)
	if should_update_password:
		reset_pass_key = _set_reset_password_key(user)
		redirect_to = f"/update-password?key={reset_pass_key}&redirect_to={redirect_to}"
	# GET requests do not cause an implicit commit
	frappe.db.commit()  # nosemgrep
	if not frappe.local.flags.in_test and not should_update_password:
		frappe.local.login_manager.login_as(invitation.email)
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = redirect_to
