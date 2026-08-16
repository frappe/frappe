# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

"""D16 -- every temporary mechanism names its own end.

The previous round of temporary mechanisms became permanent by default: nobody decided to keep
them, and nobody was ever asked to end them. `frappe/desk/RETIRING.md` is what stops that
happening twice -- one written call, naming the whole batch and the condition that fires it.

These tests keep it honest. A list nobody checks drifts into a list nobody trusts, and a batch
that has quietly lost half its members is worse than no batch at all.
"""

import os
import re

import frappe
from frappe.tests import IntegrationTestCase

RETIRING = os.path.join(frappe.get_app_path("frappe"), "desk", "RETIRING.md")

# Every mechanism in the batch, and the file a successor will be looking at when they wonder
# whether it is load-bearing. Each of these must point at `RETIRING.md` from its own source.
BATCH = (
	"frappe/desk/doctype/desktop_icon/desktop_icon.py",
	"frappe/desk/doctype/desktop_layout/desktop_layout.py",
	"frappe/desk/doctype/workspace_sidebar/workspace_sidebar.py",
	"frappe/desk/doctype/desktop_settings/desktop_settings.py",
	"frappe/desk/doctype/sidebar/convert_fixtures.py",
	"frappe/model/sync.py",
	"frappe/modules/utils.py",
	"frappe/utils/new_navigation_nudge.py",
)


def read(path: str) -> str:
	return open(os.path.join(frappe.get_app_path("frappe"), "..", path)).read()


class TestTheRetiringBatch(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.doc = open(RETIRING).read()

	def test_every_mechanism_points_at_the_call(self):
		"""The sentence has to be where a successor will actually read it -- in the file they
		are editing, not only in a document they would have to know to look for."""
		for path in BATCH:
			with self.subTest(path=path):
				self.assertIn("RETIRING.md", read(path), f"{path} does not name what ends it")

	def test_the_batch_is_written_down_in_one_place(self):
		for path in BATCH:
			with self.subTest(path=path):
				self.assertIn(os.path.basename(path).replace(".py", ""), self.doc)

	def test_every_path_it_names_still_exists(self):
		"""A batch that has quietly lost members is worse than no batch: the next maintainer
		reads a list, removes what is on it, and leaves behind whatever fell off."""
		root = os.path.join(frappe.get_app_path("frappe"), "..")
		for path in sorted(set(re.findall(r"`(frappe/[\w/]+\.?\w*)`", self.doc))):
			with self.subTest(path=path):
				self.assertTrue(os.path.exists(os.path.join(root, path)), f"{path} is named but gone")

	def test_each_line_states_a_condition_and_no_version(self):
		"""A version number fires whether or not customers moved, which turns the invitation
		into theatre. Both triggers are conditions a maintainer evaluates."""
		self.assertIn("the backport has landed and the migration is proven", self.doc)
		self.assertIn("the Apps screen is set on the majority of sites", self.doc)
		self.assertIn("No version ceiling on either line", self.doc)

	def test_the_accepted_cost_is_on_the_record(self):
		"""Including what was considered instead and why it was not enough -- otherwise a
		successor re-litigates it from scratch."""
		self.assertIn("no forcing function", self.doc)
		self.assertIn("release-checklist item", self.doc)
		self.assertIn("Adoption telemetry", self.doc)

	def test_a_decline_does_not_expire_on_a_date(self):
		"""The customer-facing half of the same rule: nothing here is removed because time
		passed."""
		self.assertIn("asked again in a later release", self.doc)
		self.assertIn("asked again in a later release", read("frappe/utils/new_navigation_nudge.py"))
