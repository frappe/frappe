# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
import frappe.utils
from frappe.model.document import Document


class UserInvitation(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		accepted_at: DF.Datetime | None
		app_name: DF.Literal[None]
		email: DF.Data
		email_sent_at: DF.Datetime | None
		invited_by: DF.Link | None
		key: DF.Data | None
		redirect_to_path: DF.Data
		role: DF.Link
		status: DF.Literal["Pending", "Accepted", "Expired"]
		user: DF.Link | None
	# end: auto-generated types

	def before_insert(self):
		frappe.utils.validate_email_address(self.email, throw=True)
		self.key = frappe.generate_hash(length=12)
		self.invited_by = frappe.session.user
		self.status = "Pending"
		if self.app_name is None:
			self.app_name = "frappe"

	def after_insert(self):
		invite_link = frappe.utils.get_url(
			f"/api/method/frappe.core.api.user_invitation.accept_invitation?key={self.key}"
		)
		email_title = self.get_email_title()
		frappe.sendmail(
			recipients=self.email,
			subject=f"You've been invited to join {email_title}",
			template="user_invitation",
			args={"title": email_title, "invite_link": invite_link, "site_name": self.get_site_name()},
			now=True,
		)
		self.db_set("email_sent_at", frappe.utils.now())

	def after_delete(self):
		if self.status == "Pending":
			email_title = self.get_email_title()
			frappe.sendmail(
				recipients=self.email,
				subject=f"Invitation to join {email_title} revoked",
				template="user_invitation_revoked",
				args={"title": email_title, "site_name": self.get_site_name()},
				now=True,
			)

	def on_update(self):
		if self.has_value_changed("status") and self.status == "Expired":
			email_title = self.get_email_title()
			frappe.sendmail(
				recipients=self.email,
				subject=f"Invitation to join {email_title} expired",
				template="user_invitation_expired",
				args={"title": email_title, "site_name": self.get_site_name()},
				now=True,
			)

	def get_email_title(self):
		return f"Frappe {(self.app_name if self.app_name != "frappe" else 'framework').capitalize()}"

	def get_redirect_to_path(self):
		return f"{'' if self.redirect_to_path.startswith('/') else '/'}{self.redirect_to_path}"

	def get_site_name(self):
		return frappe.utils.get_url(self.get_redirect_to_path())


def mark_expired_invitations() -> None:
	days = 3
	invitations_to_expire = frappe.db.get_all(
		"User Invitation",
		filters={"status": "Pending", "creation": ["<", frappe.utils.add_days(frappe.utils.now(), -days)]},
	)
	for invitation in invitations_to_expire:
		invitation = frappe.get_doc("User Invitation", invitation.name)
		invitation.status = "Expired"
		invitation.save()
