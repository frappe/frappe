# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
import frappe.utils
from frappe import _
from frappe.model.document import Document
from frappe.permissions import get_roles


class UserInvitation(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.user_role.user_role import UserRole
		from frappe.types import DF

		accepted_at: DF.Datetime | None
		app_name: DF.Literal[None]
		email: DF.Data
		email_sent_at: DF.Datetime | None
		invited_by: DF.Link | None
		key: DF.Data | None
		redirect_to_path: DF.Data
		roles: DF.TableMultiSelect[UserRole]
		status: DF.Literal["Pending", "Accepted", "Expired", "Cancelled"]
		user: DF.Link | None
	# end: auto-generated types

	def before_insert(self):
		self._validate_invite()
		self.invited_by = frappe.session.user
		self.status = "Pending"

	def after_insert(self):
		self._after_insert()

	def accept(self, ignore_permissions: bool = False):
		accepted_now = self._accept()
		if not accepted_now:
			return
		user, user_inserted = self._upsert_user(ignore_permissions)
		self.save(ignore_permissions)
		user.save(ignore_permissions)
		self._run_after_accept_hooks(user, user_inserted)

	@frappe.whitelist()
	def cancel_invite(self):
		if self.status != "Pending":
			return False
		self.status = "Cancelled"
		self.save()
		email_title = self._get_email_title()
		frappe.sendmail(
			recipients=self.email,
			subject=_("Invitation to join {0} cancelled").format(email_title),
			template="user_invitation_cancelled",
			args={"title": email_title},
			now=True,
		)
		return True

	@frappe.whitelist()
	def expire(self):
		if self.status != "Pending":
			return
		self.status = "Expired"
		self.save()
		email_title = self._get_email_title()
		invited_by_user = frappe.get_doc("User", self.invited_by)
		frappe.sendmail(
			recipients=invited_by_user.email,
			subject=_("Invitation to join {0} expired").format(email_title),
			template="user_invitation_expired",
			args={"title": email_title},
			now=False,
		)

	def _validate_invite(self):
		self._validate_app_name()
		self._validate_roles()
		self._validate_email()
		if frappe.db.get_value(
			"User Invitation", filters={"email": self.email, "status": "Accepted", "app_name": self.app_name}
		):
			frappe.throw(title=_("Error"), msg=_("invitation already accepted"))
		if frappe.db.get_value(
			"User Invitation", filters={"email": self.email, "status": "Pending", "app_name": self.app_name}
		):
			frappe.throw(title=_("Error"), msg=_("invitation already exists"))

	def _after_insert(self):
		key = frappe.generate_hash()
		self.db_set("key", frappe.utils.sha256_hash(key))
		invite_link = frappe.utils.get_url(
			f"/api/method/frappe.core.api.user_invitation.accept_invitation?key={key}"
		)
		email_title = self._get_email_title()
		frappe.sendmail(
			recipients=self.email,
			subject=_("You've been invited to join {0}").format(email_title),
			template="user_invitation",
			args={"title": email_title, "invite_link": invite_link},
			now=True,
		)
		self.db_set("email_sent_at", frappe.utils.now())
		return key

	def _accept(self):
		if self.status == "Accepted":
			return False
		if self.status == "Expired":
			frappe.throw(title=_("Error"), msg=_("Invitation is expired"))
		if self.status == "Cancelled":
			frappe.throw(title=_("Error"), msg=_("Invitation is cancelled"))
		self.status = "Accepted"
		self.accepted_at = frappe.utils.now()
		self.user = self.email
		return True

	def _upsert_user(self, ignore_permissions: bool = False):
		user: Document | None = None
		user_inserted = False
		if frappe.db.exists("User", self.user):
			user = frappe.get_doc("User", self.user)
		else:
			user = frappe.new_doc("User")
			user.user_type = "System User"
			user.email = self.email
			user.first_name = self.email.split("@")[0].title()
			user.send_welcome_email = False
			user.insert(ignore_permissions)
			user_inserted = True
		user.append_roles(*[r.role for r in self.roles])
		return user, user_inserted

	def _run_after_accept_hooks(self, user: Document, user_inserted: bool):
		user_invitation_hook = frappe.get_hooks("user_invitation", app_name=self.app_name)
		if not isinstance(user_invitation_hook, dict):
			return
		for dot_path in user_invitation_hook.get("after_accept") or []:
			frappe.call(dot_path, invitation=self, user=user, user_inserted=user_inserted)

	def _get_email_title(self):
		return frappe.get_hooks("app_title", app_name=self.app_name)[0]

	def _validate_app_name(self):
		UserInvitation.validate_app_name(self.app_name)

	def _validate_roles(self):
		if self.app_name == "frappe":
			return
		user_invitation_hook = frappe.get_hooks("user_invitation", app_name=self.app_name)
		allowed_roles: list[str] = []
		if isinstance(user_invitation_hook, dict):
			allowed_roles = user_invitation_hook.get("allowed_roles") or []
		for r in self.roles:
			if r.role in allowed_roles:
				continue
			frappe.throw(
				title=_("Invalid role"),
				msg=_("{0} is not an allowed role for {1}").format(r.role, self.app_name),
			)

	def _validate_email(self):
		frappe.utils.validate_email_address(self.email, throw=True)

	def get_redirect_to_path(self):
		start_index = 1 if self.redirect_to_path.startswith("/") else 0
		return self.redirect_to_path[start_index:]

	@staticmethod
	def validate_app_name(app_name: str):
		if app_name not in frappe.get_installed_apps():
			frappe.throw(title=_("Invalid app"), msg=_("application is not installed"))

	@staticmethod
	def validate_role(app_name: str) -> None:
		UserInvitation.validate_app_name(app_name)
		user_invitation_hook = frappe.get_hooks("user_invitation", app_name=app_name)
		only_for: list[str] = []
		if isinstance(user_invitation_hook, dict):
			only_for = user_invitation_hook.get("only_for") or []
		if "System Manager" not in only_for:
			only_for.append("System Manager")
		frappe.only_for(only_for)


def mark_expired_invitations() -> None:
	days = 3
	invitations_to_expire = frappe.db.get_all(
		"User Invitation",
		filters={"status": "Pending", "creation": ["<", frappe.utils.add_days(frappe.utils.now(), -days)]},
	)
	for invitation in invitations_to_expire:
		invitation = frappe.get_doc("User Invitation", invitation.name)
		invitation.expire()
		# to avoid losing work in case the job times out without finishing
		frappe.db.commit()  # nosemgrep


def get_allowed_apps(user: Document | None) -> list[str]:
	user_roles = set(get_user_roles(user))
	allowed_apps: list[str] = []
	for app in frappe.get_installed_apps():
		user_invitation_hooks = frappe.get_hooks("user_invitation", app_name=app)
		if not isinstance(user_invitation_hooks, dict):
			continue
		only_for = user_invitation_hooks.get("only_for") or []
		if set(only_for) & user_roles:
			allowed_apps.append(app)
	return allowed_apps


def get_permission_query_conditions(user: Document | None) -> str | None:
	user = get_user(user)
	user_roles = get_user_roles(user)
	if "System Manager" in user_roles:
		return
	allowed_apps = get_allowed_apps(user)
	if not allowed_apps:
		return "false"
	allowed_apps_str = ", ".join([f'"{app}"' for app in allowed_apps])
	return f"`tabUser Invitation`.app_name IN ({allowed_apps_str})"


def has_permission(
	doc: UserInvitation, user: Document | None = None, permission_type: str | None = None
) -> bool:
	return permission_type != "delete" and doc.app_name in get_allowed_apps(user)


def get_user_roles(user: Document | None) -> list[str]:
	return get_roles(get_user(user))


def get_user(user: Document | None) -> Document:
	return user or frappe.session.user
