# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document
from frappe.query_builder import Interval
from frappe.query_builder.functions import Now
from frappe.utils.data import add_to_date, sha256_hash


def get_oauth_token_hash(token: str | bytes | None) -> str | None:
	if not token:
		return None
	return sha256_hash(token)


class OAuthBearerToken(Document):
	_DOCTYPE_NAME = "OAuth Bearer Token"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		access_token: DF.Data | None
		client: DF.Link | None
		expiration_time: DF.Datetime | None
		expires_in: DF.Int
		refresh_token: DF.Data | None
		scopes: DF.Text | None
		status: DF.Literal["Active", "Revoked"]
		user: DF.Link
	# end: auto-generated types

	def before_insert(self):
		if self.access_token:
			self.access_token = get_oauth_token_hash(self.access_token)
		if self.refresh_token:
			self.refresh_token = get_oauth_token_hash(self.refresh_token)

	def validate(self):
		if not self.expiration_time:
			self.expiration_time = add_to_date(self.creation, seconds=self.expires_in, as_datetime=True)

	@staticmethod
	def clear_old_logs(days=30):
		table = frappe.qb.DocType("OAuth Bearer Token")
		frappe.db.delete(
			table,
			filters=(table.expiration_time < (Now() - Interval(days=days))),
		)
