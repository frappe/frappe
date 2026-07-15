from frappe.patches.v17_0.dedupe_and_harden_user_email import _normalize, plan_dedupe
from frappe.tests import UnitTestCase


def _u(name, email, enabled=1):
	return {"name": name, "email": email, "enabled": enabled}


def _apply(users, changes):
	"""Apply the planned rewrites and return the resulting rows."""
	by_name = {u["name"]: dict(u) for u in users}
	for name, old, new in changes:
		assert by_name[name]["email"] == old
		by_name[name]["email"] = new
	return list(by_name.values())


class TestUserEmailDedupe(UnitTestCase):
	"""Unit tests for the pure planning step of the email-hardening patch. No DB -- these assert
	the invariants the unique index depends on: every planned outcome is globally unique,
	non-empty, and stable under a second planning pass (idempotent)."""

	def assertClean(self, users):
		"""Plan, apply, and assert uniqueness + non-emptiness + idempotency. Returns changes."""
		changes = plan_dedupe(users)
		after = _apply(users, changes)

		emails = [_normalize(u["email"]) for u in after]
		self.assertEqual(len(emails), len(set(emails)), f"emails not unique: {emails}")
		self.assertTrue(all(emails), f"empty email survived: {emails}")
		self.assertEqual(plan_dedupe(after), [], "planning is not idempotent")
		return changes, {u["name"]: u["email"] for u in after}

	def test_clean_data_is_untouched(self):
		changes, _ = self.assertClean([_u("a@x.com", "a@x.com"), _u("b@x.com", "b@x.com")])
		self.assertEqual(changes, [])

	def test_enabled_login_named_user_keeps_the_address(self):
		# The account whose name IS the email wins; the other is re-addressed to its own name.
		_, emails = self.assertClean([_u("a@x.com", "dup@x.com"), _u("dup@x.com", "dup@x.com")])
		self.assertEqual(emails["dup@x.com"], "dup@x.com")
		self.assertEqual(emails["a@x.com"], "a@x.com")

	def test_enabled_user_beats_disabled_one(self):
		_, emails = self.assertClean(
			[_u("main@x.com", "shared@x.com", 1), _u("old@x.com", "shared@x.com", 0)]
		)
		self.assertEqual(emails["main@x.com"], "shared@x.com")

	def test_standard_user_yields_to_real_user_and_restores_default(self):
		_, emails = self.assertClean([_u("Administrator", "shared@x.com"), _u("real@x.com", "shared@x.com")])
		self.assertEqual(emails["real@x.com"], "shared@x.com")
		self.assertEqual(emails["Administrator"], "admin@example.com")

	def test_standard_default_collision_falls_back_to_plus_tag(self):
		_, emails = self.assertClean(
			[_u("Administrator", "admin@example.com"), _u("x@x.com", "admin@example.com")]
		)
		self.assertEqual(emails["x@x.com"], "admin@example.com")
		self.assertEqual(emails["Administrator"], "admin+administrator@example.com")

	def test_administrator_and_guest_both_collide(self):
		_, emails = self.assertClean(
			[
				_u("Administrator", "team@x.com"),
				_u("Guest", "team@x.com"),
				_u("real@x.com", "team@x.com"),
			]
		)
		self.assertEqual(emails["real@x.com"], "team@x.com")
		self.assertEqual(emails["Administrator"], "admin@example.com")
		self.assertEqual(emails["Guest"], "guest@example.com")

	def test_case_and_whitespace_variants_are_deduped(self):
		self.assertClean([_u("a@x.com", "  DUP@X.com "), _u("b@x.com", "dup@x.com")])

	def test_blank_and_null_emails_get_unique_addresses(self):
		# reqd field that has drifted to empty/NULL -- everyone must end up with a real address.
		self.assertClean([_u("u1@x.com", ""), _u("u2@x.com", None), _u("SERIES-0001", "")])

	def test_many_series_named_losers_get_incrementing_tags(self):
		_, emails = self.assertClean(
			[
				_u("SER-1", "hub@x.com"),
				_u("SER-2", "hub@x.com"),
				_u("SER-3", "hub@x.com"),
				_u("hub@x.com", "hub@x.com"),
			]
		)
		self.assertEqual(emails["hub@x.com"], "hub@x.com")
		self.assertEqual(len({v for v in emails.values()}), 4)
