import frappe
import frappe.utils
from frappe import _
from frappe.core.doctype.user_invitation.user_invitation import UserInvitation


@frappe.whitelist(methods=["POST"])
def invite_by_email(
	emails: str, roles: list[str], redirect_to_path: str, app_name: str = "frappe"
) -> dict[str, list[str]]:
	# validate `app_name`
	UserInvitation.validate_app_name(app_name)

	user_invitation_hook = frappe.get_hooks("user_invitation", app_name=app_name)

	# check `only_for`
	only_for = ["System Manager"]
	if app_name != "frappe":
		if isinstance(user_invitation_hook, dict):
			only_for = user_invitation_hook.get("only_for") or []
		else:
			only_for = []
	frappe.only_for(only_for)

	# validate emails
	frappe.utils.validate_email_address(emails, throw=True)
	email_list = frappe.utils.split_emails(emails)
	if not email_list:
		frappe.throw(title=_("Invalid input"), msg=_("no email addresses to invite"))

	# get relevant data from the database
	existing_user_emails = frappe.db.get_all("User", filters={"email": ["in", email_list]}, pluck="email")
	existing_invited_emails = frappe.db.get_all(
		"User Invitation",
		filters={"email": ["in", email_list], "status": "Pending", "app_name": app_name},
		pluck="email",
	)

	# create invitation documents
	to_invite = list(set(email_list) - set(existing_user_emails) - set(existing_invited_emails))
	for email in to_invite:
		frappe.get_doc(
			doctype="User Invitation",
			email=email,
			roles=[dict(role=role) for role in roles],
			app_name=app_name,
			redirect_to_path=redirect_to_path,
		).insert()

	return {
		"existing_user_emails": existing_user_emails,
		"existing_invited_emails": existing_invited_emails,
		"invited_emails": to_invite,
	}


@frappe.whitelist(allow_guest=True, methods=["GET"])
def accept_invitation(key: str) -> None:
	_accept_invitation(key, False)


def _accept_invitation(key: str, in_test: bool) -> None:
	# get invitation
	hashed_key = frappe.utils.sha256_hash(key)
	invitation_name = frappe.db.get_value("User Invitation", filters={"key": hashed_key})
	if not invitation_name:
		frappe.throw(title=_("Error"), msg=_("Invalid key"))
	invitation = frappe.get_doc("User Invitation", invitation_name)

	# accept invitation
	invitation.accept(ignore_permissions=True)

	user = frappe.get_doc("User", invitation.email)
	should_update_password = not user.last_password_reset_date and not bool(
		frappe.get_system_settings("disable_user_pass_login")
	)

	# set redirect_to
	redirect_to = frappe.utils.get_url(invitation.get_redirect_to_path())
	if should_update_password:
		redirect_to = f"{user.reset_password()}&redirect_to=/{invitation.get_redirect_to_path()}"

	# GET requests do not cause an implicit commit
	frappe.db.commit()  # nosemgrep

	if not in_test and not should_update_password:
		frappe.local.login_manager.login_as(invitation.email)

	# set response
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = redirect_to
