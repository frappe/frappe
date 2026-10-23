"""Explicit browse targets can be real sites or symlinked sites."""

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from click.testing import CliRunner

from frappe.commands.site import browse


class BrowseSiteTest(unittest.TestCase):
	def test_browse_accepts_a_symlink_to_a_site(self):
		runner = CliRunner()
		with runner.isolated_filesystem():
			Path("restored").mkdir()
			Path("restored/site_config.json").write_text("{}")
			Path("rehearsal.localhost").symlink_to("restored", target_is_directory=True)
			with (
				patch("frappe.init") as init,
				patch("frappe.connect"),
				patch("frappe.utils.get_sites", return_value=[]),
				patch("frappe.utils.get_site_url", return_value="http://rehearsal.localhost:8006"),
				patch("click.launch") as launch,
			):
				result = runner.invoke(
					browse, obj=SimpleNamespace(sites=["rehearsal.localhost"], profile=False)
				)
				self.assertEqual(result.exit_code, 0, result.output)
				init.assert_called_once_with("rehearsal.localhost")
				launch.assert_called_once_with("http://rehearsal.localhost:8006")

	def test_browse_refuses_a_missing_or_broken_symlinked_site(self):
		runner = CliRunner()
		with runner.isolated_filesystem():
			Path("broken.localhost").symlink_to("missing", target_is_directory=True)
			Path("empty.localhost").mkdir()
			for site in ("missing.localhost", "broken.localhost", "empty.localhost"):
				with (
					self.subTest(site=site),
					patch("frappe.utils.get_sites", return_value=[]),
					patch("frappe.init") as init,
				):
					result = runner.invoke(browse, obj=SimpleNamespace(sites=[site], profile=False))
					self.assertEqual(result.exit_code, 1)
					self.assertIn("doesn't exist", result.output)
					init.assert_not_called()
