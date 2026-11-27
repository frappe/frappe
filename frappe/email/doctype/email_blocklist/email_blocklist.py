# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import re
from functools import cache

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import validate_email_address

DOMAIN_PATTERN = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$")


class EmailBlocklist(Document):
	_DOCTYPE_NAME = "Email Blocklist"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		email_or_domain: DF.Data
	# end: auto-generated types

	def before_naming(self):
		self.email_or_domain = self.email_or_domain.strip().lower()

	def validate(self):
		if "@" in self.email_or_domain:
			validate_email_address(self.email_or_domain, throw=True)
		elif not DOMAIN_PATTERN.match(self.email_or_domain):
			frappe.throw(
				_("{0} is not a valid domain").format(frappe.bold(self.email_or_domain)),
				title=_("Invalid Domain"),
			)


@cache
def get_shipped_blocked_domains() -> frozenset[str]:
	with open(frappe.get_app_path("frappe", "email", "blocked_email_domains.txt")) as file:
		lines = (line.strip().lower() for line in file)
		return frozenset(line for line in lines if line and not line.startswith("#"))


def get_domain_with_parents(email: str) -> list[str]:
	"""Return `a.b.com` as `["a.b.com", "b.com"]`, without the bare top-level domain."""
	parts = email.rsplit("@", 1)[-1].lower().split(".")
	return [".".join(parts[index:]) for index in range(len(parts) - 1)]


def get_blocked_emails(emails: list[str]) -> list[str]:
	"""Return the emails the site must not send to, from the Email Blocklist and the shipped domain list."""
	domains_by_email = {email: get_domain_with_parents(email) for email in emails}
	entries = {email.lower() for email in emails}.union(*domains_by_email.values())
	site_blocked = set(
		frappe.get_all("Email Blocklist", filters={"name": ("in", list(entries))}, pluck="name")
	)
	shipped_blocked = get_shipped_blocked_domains()
	allowed = {domain.lower() for domain in frappe.conf.get("allow_blocked_email_domains") or []}

	return [
		email
		for email, domains in domains_by_email.items()
		if email.lower() in site_blocked
		or site_blocked.intersection(domains)
		or (shipped_blocked.intersection(domains) and not allowed.intersection(domains))
	]
