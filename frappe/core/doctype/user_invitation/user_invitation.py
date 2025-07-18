# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
import frappe.utils
from frappe import _
from frappe.model.document import Document


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
		user = self._upsert_user()
		self.save(ignore_permissions)
		user.save(ignore_permissions)
		self._run_after_accept_hooks(user)

	@frappe.whitelist()
	def cancel_invite(self):
		if self.status == "Cancelled":
			return
		prev_status = self.status
		self.status = "Cancelled"
		self.save()
		if prev_status == "Pending":
			email_title = self._get_email_title()
			frappe.sendmail(
				recipients=self.email,
				subject=_("Invitation to join {0} cancelled").format(email_title),
				template="user_invitation_cancelled",
				args={"title": email_title, "site_name": self._get_site_name()},
				now=True,
			)

	@frappe.whitelist()
	def expire(self):
		if self.status == "Expired":
			return
		prev_status = self.status
		self.status = "Expired"
		self.save()
		if prev_status == "Pending":
			email_title = self._get_email_title()
			invited_by_user = frappe.get_doc("User", self.invited_by)
			frappe.sendmail(
				recipients=invited_by_user.email,
				subject=_("Invitation to join {0} expired").format(email_title),
				template="user_invitation_expired",
				args={"title": email_title, "site_name": self._get_site_name()},
				now=False,
			)

	def _validate_invite(self):
		self._validate_app_name()
		self._validate_roles()
		self._validate_email()
		if frappe.db.get_value(
			"User Invitation", filters={"email": self.email, "status": "Pending", "app_name": self.app_name}
		):
			frappe.throw(title=_("Error"), msg=_("Invitation already exists"))

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
			args={"title": email_title, "invite_link": invite_link, "site_name": self._get_site_name()},
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

	def _upsert_user(self):
		user: Document | None = None
		if frappe.db.exists("User", self.user):
			user = frappe.get_doc("User", self.user)
		else:
			user = frappe.new_doc("User")
			user.user_type = "System User"
			user.email = self.email
			user.first_name = self.email.split("@")[0].title()
			user.send_welcome_email = False
			user.insert()
		user.append_roles(*[r.role for r in self.roles])
		return user

	def _run_after_accept_hooks(self, user: Document):
		user_invitation_hook = frappe.get_hooks("user_invitation", app_name=self.app_name)
		if not isinstance(user_invitation_hook, dict):
			return
		for dot_path in user_invitation_hook.get("after_accept") or []:
			frappe.call(dot_path, invitation=self, user=user)

	def _get_email_title(self):
		return frappe.get_hooks("app_title", app_name=self.app_name)[0]

	def _get_site_name(self):
		return frappe.utils.get_url(self.get_redirect_to_path())

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
		if frappe.db.exists("User", self.email):
			frappe.throw(title=_("Invalid email"), msg=_("User already exists"))

	@classmethod
	def validate_app_name(cls, app_name: str):
		if app_name not in frappe.get_installed_apps():
			frappe.throw(title=_("Invalid app"), msg=_("application is not installed"))

	def get_redirect_to_path(self):
		start_index = 1 if self.redirect_to_path.startswith("/") else 0
		return self.redirect_to_path[start_index:]


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
