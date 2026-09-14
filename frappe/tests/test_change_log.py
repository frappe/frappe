# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from semantic_version import Version

from frappe.tests import UnitTestCase
from frappe.utils.change_log import parse_latest_non_beta_release


class TestChangeLog(UnitTestCase):
	def test_parse_latest_non_beta_release_skips_non_semver_tags(self):
		releases = [
			{"tag_name": "v14-baseline", "prerelease": False},
			{"tag_name": "invalid-tag", "prerelease": False},
			{"tag_name": "v14.1.0", "prerelease": False},
			{"tag_name": "v14.0.0", "prerelease": False},
		]
		latest = parse_latest_non_beta_release(releases, Version("14.0.0"))
		self.assertEqual(latest, "14.1.0")

	def test_parse_latest_non_beta_release_only_non_semver_tags(self):
		releases = [
			{"tag_name": "v14-baseline", "prerelease": False},
			{"tag_name": "nightly", "prerelease": False},
		]
		latest = parse_latest_non_beta_release(releases, Version("14.0.0"))
		self.assertIsNone(latest)

	def test_parse_latest_non_beta_release_skips_prereleases(self):
		releases = [
			{"tag_name": "v14.2.0-beta.1", "prerelease": True},
			{"tag_name": "v14.1.0", "prerelease": False},
		]
		latest = parse_latest_non_beta_release(releases, Version("14.0.0"))
		self.assertEqual(latest, "14.1.0")

	def test_parse_latest_non_beta_release_prioritizes_same_major(self):
		releases = [
			{"tag_name": "v14.8.0", "prerelease": False},
			{"tag_name": "v15.1.0", "prerelease": False},
		]
		latest_v14 = parse_latest_non_beta_release(releases, Version("14.5.0"))
		self.assertEqual(latest_v14, "14.8.0")

		latest_v15 = parse_latest_non_beta_release(releases, Version("15.0.0"))
		self.assertEqual(latest_v15, "15.1.0")

	def test_parse_latest_non_beta_release_edge_cases(self):
		self.assertIsNone(parse_latest_non_beta_release([], Version("14.0.0")))

		releases_with_empty_or_none = [
			{"tag_name": None, "prerelease": False},
			{"tag_name": "", "prerelease": False},
			{"tag_name": "14.2.0", "prerelease": False},
		]
		latest = parse_latest_non_beta_release(releases_with_empty_or_none, Version("14.0.0"))
		self.assertEqual(latest, "14.2.0")
