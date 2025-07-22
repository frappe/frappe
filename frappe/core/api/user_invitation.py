import frappe
import frappe.utils
from frappe import _
from frappe.core.doctype.user_invitation.user_invitation import UserInvitation


@frappe.whitelist(methods=["POST"])
def invite_by_email(
	emails: str, roles: list[str], redirect_to_path: str, app_name: str = "frappe"
) -> dict[str, list[str]]:
	_app_only_for(app_name)

	# validate emails
	frappe.utils.validate_email_address(emails, throw=True)
	email_list = frappe.utils.split_emails(emails)
	if not email_list:
		frappe.throw(title=_("Invalid input"), msg=_("no email addresses to invite"))

	# get relevant data from the database
	accepted_invite_emails = frappe.db.get_all(
		"User Invitation",
		filters={"email": ["in", email_list], "status": "Accepted", "app_name": app_name},
		pluck="email",
	)
	pending_invite_emails = frappe.db.get_all(
		"User Invitation",
		filters={"email": ["in", email_list], "status": "Pending", "app_name": app_name},
		pluck="email",
	)

	# create invitation documents
	to_invite = list(set(email_list) - set(accepted_invite_emails) - set(pending_invite_emails))
	for email in to_invite:
		frappe.get_doc(
			doctype="User Invitation",
			email=email,
			roles=[dict(role=role) for role in roles],
			app_name=app_name,
			redirect_to_path=redirect_to_path,
		).insert()

	return {
		"accepted_invite_emails": accepted_invite_emails,
		"pending_invite_emails": pending_invite_emails,
		"invited_emails": to_invite,
	}


@frappe.whitelist(allow_guest=True, methods=["GET"])
def accept_invitation(key: str) -> None:
	_accept_invitation(key, False)


# `app_name` is required for security
@frappe.whitelist(methods=["PATCH"])
def cancel_invitation(name: str, app_name: str):
	_app_only_for(app_name)

	if not frappe.db.exists("User Invitation", name):
		frappe.throw(title=_("Error"), msg=_("invitation not found"))

	invitation = frappe.get_doc("User Invitation", name)
	if invitation.app_name != app_name:
		# message is not specific enough for security
		frappe.throw(title=_("Error"), msg=_("invitation not found"))

	if invitation.status == "Cancelled":
		return {"cancelled_now": False}

	if invitation.status != "Pending":
		frappe.throw(title=_("Error"), msg=_("invitation cannot be cancelled"))

	return {"cancelled_now": invitation.cancel_invite()}


@frappe.whitelist(methods=["GET"])
def get_pending_invitations(app_name: str):
	_app_only_for(app_name)

	return list(
		map(
			lambda invite: {
				"name": invite.name,
				"email": invite.email,
				"roles": list(
					map(
						lambda r: r.role,
						frappe.db.get_all(
							"User Role",
							fields=["role"],
							filters={"parent": invite.name},
							ignore_permissions=True,
						),
					)
				),
			},
			frappe.db.get_all(
				"User Invitation",
				fields=["name", "email"],
				filters={"status": "Pending", "app_name": app_name},
				ignore_permissions=True,
			),
		)
	)


def _app_only_for(app_name: str):
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
