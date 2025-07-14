import frappe

USER_INVITATION_DOCTYPE = "User Invitation"
FRAMEWORK_APP_NAME = " "


@frappe.whitelist()
def invite_by_email(
	emails: str, role: str, redirect_to_path: str, app_name: str = FRAMEWORK_APP_NAME
) -> dict[str, list[str]]:
	frappe.only_for(["System Manager", "User Invitation Manager"])
	is_app_framework = app_name == FRAMEWORK_APP_NAME
	allowed_roles: list[str] = []
	if not is_app_framework:
		# `role` validation
		invalid_app_msg = frappe._("Invalid app")
		try:
			user_invitation_hook = frappe.get_hooks("user_invitation", app_name=app_name)
			allowed_invite_roles_key = "allowed_invite_roles"
			if (
				not isinstance(user_invitation_hook, dict)
				or not isinstance(user_invitation_hook.get(allowed_invite_roles_key), list)
				or not all(isinstance(r, str) for r in user_invitation_hook.get(allowed_invite_roles_key))
			):
				frappe.throw(invalid_app_msg)
			allowed_roles = user_invitation_hook.get(allowed_invite_roles_key)
			if not allowed_roles:
				frappe.throw(invalid_app_msg)
		except ImportError:
			frappe.throw(invalid_app_msg)
		if role not in allowed_roles:
			frappe.throw(frappe._("Invalid role"))
	frappe.utils.validate_email_address(emails, throw=True)
	email_list = frappe.utils.split_emails(emails)
	if not email_list:
		frappe.throw(frappe._("No email addresses found"))
	existing_user_emails = frappe.db.get_all("User", filters={"email": ["in", email_list]}, pluck="email")
	existing_invited_emails_filters = {"email": ["in", email_list]}
	if not is_app_framework:
		existing_invited_emails_filters["role"] = ["in", allowed_roles]
	existing_invited_emails = frappe.db.get_all(
		USER_INVITATION_DOCTYPE, filters=existing_invited_emails_filters, pluck="email"
	)
	to_invite = list(set(email_list) - set(existing_user_emails) - set(existing_invited_emails))
	for email in to_invite:
		frappe.get_doc(
			doctype=USER_INVITATION_DOCTYPE,
			email=email,
			role=role,
			app_name=app_name,
			redirect_to_path=redirect_to_path,
		).insert()
	return {
		"existing_user_emails": existing_user_emails,
		"existing_invited_emails": existing_invited_emails,
		"invited_emails": to_invite,
	}


@frappe.whitelist(allow_guest=True)
def accept_invitation(key: str) -> None:
	result = frappe.db.get_all(USER_INVITATION_DOCTYPE, filters={"key": key}, pluck="name")
	invalid_or_expired_key_msg = frappe._("Invalid or expired key")
	if not result:
		frappe.throw(invalid_or_expired_key_msg)
	invitation = frappe.get_doc(USER_INVITATION_DOCTYPE, result[0])
	if invitation.status == "Expired":
		frappe.throw(invalid_or_expired_key_msg)
	if invitation.status == "Pending":
		user = invitation.create_user_if_not_exists(ignore_permissions=True)
		user.append_roles(invitation.role)
		user.save(ignore_permissions=True)
		invitation.status = "Accepted"
		invitation.accepted_at = frappe.utils.now()
		invitation.user = user.email
		invitation.save(ignore_permissions=True)
		after_accept_fns = []
		if invitation.app_name != " ":
			try:
				user_invitation_hook = frappe.get_hooks("user_invitation", app_name=invitation.app_name)
				after_accept_key = "after_accept"
				# assume the values will always be valid dot paths to functions
				if isinstance(user_invitation_hook, dict) and isinstance(
					user_invitation_hook.get(after_accept_key), list
				):
					for after_accept in user_invitation_hook.get(after_accept_key):
						if isinstance(after_accept, str):
							after_accept_fns.append(frappe.get_attr(after_accept))
			except Exception:
				pass
		for after_accept_fn in after_accept_fns:
			after_accept_fn(invitation)
	user = frappe.get_doc("User", invitation.email)
	should_update_password = not user.last_password_reset_date and not bool(
		frappe.get_system_settings("disable_user_pass_login")
	)
	redirect_to = invitation.get_redirect_to_path()
	if should_update_password:
		key = frappe.generate_hash()
		hashed_key = frappe.utils.sha256_hash(key)
		user.reset_password_key = hashed_key
		user.last_reset_password_key_generated_on = frappe.utils.now_datetime()
		user.save(ignore_permissions=True)
		redirect_to = f"/update-password?key={key}&redirect_to={redirect_to}"
	# GET requests do not cause an implicit commit
	frappe.db.commit()  # nosemgrep
	if not frappe.local.flags.in_test and not should_update_password:
		frappe.local.login_manager.login_as(invitation.email)
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = redirect_to
