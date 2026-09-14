# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class RateLimit(Document):
	def validate(self) -> None:
		self.validate_method_path()
		self.validate_strategy()
		self.validate_value()
		self.validate_methods()
		self.validate_allowed_and_blocked_ips()
		self.validate_no_duplicate_scope()

	def on_update(self) -> None:
		self.clear_cache()

	def on_trash(self) -> None:
		self.clear_cache()

	def validate_method_path(self) -> None:
		try:
			fn = frappe.get_attr(self.method_path)
		except Exception:
			frappe.throw(_("Method path <code>{0}</code> is invalid or not found.").format(self.method_path))

		if not getattr(fn, "_is_dynamic_rate_limited", False):
			frappe.throw(
				_(
					"The method <code>{0}</code> is missing the required <code>@dynamic_rate_limit</code> decorator."
				).format(self.method_path)
			)

	def validate_strategy(self) -> None:
		if not self.key_ and not self.ip_based and not self.user_based:
			frappe.throw(_("At least one strategy (Key, IP, or User based) must be selected."))

	def validate_value(self) -> None:
		if self.value and not self.key_:
			frappe.throw(
				_("{0} is required when {1} is set.").format(frappe.bold(_("Key")), frappe.bold(_("Value")))
			)

	def validate_methods(self) -> None:
		if self.methods:
			methods = [m.strip().upper() for m in self.methods.split("\n") if m.strip()]
			self.methods = "\n".join(dict.fromkeys(methods))

	def validate_allowed_and_blocked_ips(self) -> None:
		allowed_and_blocked_ips = set()
		for ip_type in ["allowed_ips", "blocked_ips"]:
			ips = []
			if getattr(self, ip_type):
				for ip in getattr(self, ip_type).split("\n"):
					ip = ip.strip()
					if ip and ip not in ips:
						if ip in allowed_and_blocked_ips:
							frappe.throw(_("{0} cannot be both allowed and blocked.").format(frappe.bold(ip)))
						ips.append(ip)
						allowed_and_blocked_ips.add(ip)
			setattr(self, ip_type, "\n".join(ips))

	def validate_no_duplicate_scope(self) -> None:
		filters = {
			"method_path": self.method_path,
			"key_": self.key_ or "",
			"value": self.value or "",
			"ip_based": self.ip_based,
			"user_based": self.user_based,
			"seconds": self.seconds,
			"name": ("!=", self.name),
		}
		if frappe.db.exists("Rate Limit", filters):
			frappe.throw(
				_("A Rate Limit rule with the exact same scope already exists for {0}.").format(
					self.method_path
				),
				frappe.DuplicateEntryError,
			)

	def on_doctype_update():
		"""Ensure the multi-column unique constraint is applied every time the schema syncs."""

	frappe.db.add_unique(
		"Rate Limit",
		["method_path", "key_", "value", "ip_based", "user_based", "seconds"],
		constraint_name="unique_rate_limit",
	)

	def clear_cache(self) -> None:
		frappe.cache.hdel("rate_limits", self.method_path)


def get_rate_limits(method_path: str) -> list:
	"""Returns the rate limits for the method path."""

	def generator() -> list:
		RATE_LIMIT = frappe.qb.DocType("Rate Limit")

		fields = [
			RATE_LIMIT.ignore_in_developer_mode,
			RATE_LIMIT.key_.as_("key"),
			RATE_LIMIT.value,
			RATE_LIMIT.limit,
			RATE_LIMIT.seconds,
			RATE_LIMIT.methods,
			RATE_LIMIT.ip_based,
			RATE_LIMIT.allowed_ips,
			RATE_LIMIT.blocked_ips,
		]

		if frappe.db.has_column("Rate Limit", "user_based"):
			fields.append(RATE_LIMIT.user_based)

		rate_limits = (
			frappe.qb.from_(RATE_LIMIT)
			.select(*fields)
			.where((RATE_LIMIT.enabled == 1) & (RATE_LIMIT.method_path == method_path))
		).run(as_dict=True)

		for rl in rate_limits:
			rl["ignore_in_developer_mode"] = bool(rl["ignore_in_developer_mode"])
			rl["ip_based"] = bool(rl["ip_based"])
			rl["user_based"] = bool(rl.get("user_based"))
			rl["methods"] = rl["methods"].split("\n") if rl["methods"] else []

			if len(rl["methods"]) == 1 and rl["methods"][0] == "ALL":
				rl["methods"] = "ALL"

			rl["allowed_ips"] = rl["allowed_ips"].split("\n") if rl.get("allowed_ips") else []
			rl["blocked_ips"] = rl["blocked_ips"].split("\n") if rl.get("blocked_ips") else []

		return rate_limits

	return frappe.cache.hget("rate_limits", method_path, generator)
