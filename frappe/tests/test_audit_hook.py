import os
import subprocess
import sys
import tempfile
from typing import ClassVar

from frappe._audit_hook import is_allowed_path, is_inside
from frappe.tests import UnitTestCase

# The hook can not be uninstalled once added, so block mode has to be exercised in a fresh
# interpreter. Running it in-process would apply it to every test that follows.
BLOCK_MODE_SCRIPT = """
import sys

import frappe

frappe.local.audit_roots = {"trusted": (sys.prefix,), "untrusted": ()}

try:
	open("/etc/hosts").close()
except PermissionError:
	print("blocked")
else:
	print("allowed")
"""


class TestAuditHook(UnitTestCase):
	def setUp(self):
		super().setUp()
		self.roots = {
			"trusted": ("/frappe-bench/apps", "/frappe-bench/sites/test.local"),
			"untrusted": ("/tmp",),
		}

	def test_allows_paths_inside_roots(self):
		self.assertTrue(is_allowed_path("/frappe-bench/apps/frappe/hooks.py", self.roots))
		self.assertTrue(is_allowed_path("/frappe-bench/sites/test.local/public/files/a.png", self.roots))

	def test_allows_the_root_itself(self):
		self.assertTrue(is_allowed_path("/frappe-bench/apps", self.roots))

	def test_blocks_paths_outside_roots(self):
		self.assertFalse(is_allowed_path("/etc/passwd", self.roots))
		self.assertFalse(is_allowed_path("/frappe-bench/sites/common_site_config.json", self.roots))

	def test_blocks_sibling_with_shared_prefix(self):
		self.assertFalse(is_allowed_path("/frappe-bench/apps-evil/payload.py", self.roots))

	def test_blocks_traversal_out_of_site(self):
		escape = "/frappe-bench/sites/test.local/public/../../other.local/site_config.json"
		self.assertFalse(is_allowed_path(escape, self.roots))

	def test_blocks_absolute_path_injection(self):
		self.assertEqual(os.path.join("/frappe-bench/sites/test.local", "/etc/passwd"), "/etc/passwd")
		self.assertFalse(is_allowed_path("/etc/passwd", self.roots))

	def test_resolves_symlinks_before_deciding(self):
		with tempfile.TemporaryDirectory() as tmp:
			link = os.path.join(tmp, "escape")
			os.symlink("/etc/hosts", link)
			test_roots = {"trusted": (), "untrusted": (tmp,)}
			self.assertFalse(is_allowed_path(link, test_roots))

	def test_trusted_roots_skip_symlink_resolution(self):
		with tempfile.TemporaryDirectory() as tmp:
			link = os.path.join(tmp, "escape")
			os.symlink("/etc/hosts", link)
			self.assertTrue(is_allowed_path(link, {"trusted": (tmp,), "untrusted": ()}))

	def test_is_inside(self):
		self.assertTrue(is_inside("/a/b", ("/a",)))
		self.assertTrue(is_inside("/a", ("/a",)))
		self.assertFalse(is_inside("/ab", ("/a",)))
		self.assertFalse(is_inside("/a", ()))

	def test_block_mode_denies_access(self):
		result = subprocess.run(
			[sys.executable, "-c", BLOCK_MODE_SCRIPT],
			env={**os.environ, "FRAPPE_AUDIT_HOOK_MODE": "block", "FRAPPE_STREAM_LOGGING": "1"},
			capture_output=True,
			text=True,
		)
		self.assertIn("blocked", result.stdout, msg=result.stderr)
