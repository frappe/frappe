import json
import os
import subprocess
import sys
import tempfile

import frappe
from frappe._audit_hook import is_allowed_path, is_inside
from frappe.tests import UnitTestCase

ROOTS = {
	"read": ("/frappe-bench/apps",),
	"write": ("/frappe-bench/sites/test.local",),
	"config": frozenset(("/frappe-bench/sites/test.local/site_config.json",)),
}

# The hook can not be uninstalled once added, so block mode has to be exercised in a fresh
# interpreter. Running it in-process would apply it to every test that follows.
BLOCK_MODE_SCRIPT = """
import json
import os
import subprocess
import tempfile

import frappe
import frappe._audit_hook as audit_hook

config_file = os.path.realpath("common_site_config.json")
hooks_py = frappe.get_app_path("frappe", "hooks.py")
frappe.local.audit_roots = {
	"read": audit_hook.read_roots,
	"write": audit_hook.write_roots,
	"config": frozenset((config_file,)),
}


def refused(fn):
	try:
		fn()
	except PermissionError:
		return True
	return False


def nested_rmtree():
	with tempfile.TemporaryDirectory() as tmp:
		os.makedirs(os.path.join(tmp, "a", "b"))
		open(os.path.join(tmp, "a", "b", "f.txt"), "w").close()


print(json.dumps({
	"traversal is refused": refused(lambda: open("/etc/passwd").close()),
	"a repeated attempt is still refused": refused(lambda: open("/etc/passwd").close()),
	"code is readable": not refused(lambda: open(hooks_py).close()),
	"code is not writable": refused(lambda: open(hooks_py, "a").close()),
	"subprocess.DEVNULL works": not refused(lambda: subprocess.run(["true"], stdout=subprocess.DEVNULL)),
	"nested rmtree works": not refused(nested_rmtree),
	"config reads through frappe.config": not refused(lambda: frappe.get_common_site_config(".")),
	"config refuses a direct open": refused(lambda: open(config_file).close()),
}))
"""


class TestAuditHook(UnitTestCase):
	def test_reads_allowed_in_read_roots(self):
		self.assertTrue(is_allowed_path("/frappe-bench/apps/frappe/hooks.py", ROOTS, is_write=False))

	def test_code_directories_are_not_writable(self):
		self.assertFalse(is_allowed_path("/frappe-bench/apps/frappe/hooks.py", ROOTS, is_write=True))

	def test_site_is_readable_and_writable(self):
		path = "/frappe-bench/sites/test.local/public/files/a.png"
		self.assertTrue(is_allowed_path(path, ROOTS, is_write=False))
		self.assertTrue(is_allowed_path(path, ROOTS, is_write=True))

	def test_blocks_paths_outside_roots(self):
		self.assertFalse(is_allowed_path("/etc/passwd", ROOTS, is_write=False))
		self.assertFalse(
			is_allowed_path("/frappe-bench/sites/other.local/site_config.json", ROOTS, is_write=False)
		)

	def test_blocks_sibling_with_shared_prefix(self):
		self.assertFalse(is_allowed_path("/frappe-bench/apps-evil/payload.py", ROOTS, is_write=False))

	def test_blocks_traversal_out_of_site(self):
		escape = "/frappe-bench/sites/test.local/public/../../other.local/site_config.json"
		self.assertFalse(is_allowed_path(escape, ROOTS, is_write=False))

	def test_blocks_absolute_path_injection(self):
		# os.path.join() discards everything left of an absolute component, so this escapes
		# without containing a single "..".
		self.assertEqual(os.path.join("/frappe-bench/sites/test.local", "/etc/passwd"), "/etc/passwd")
		self.assertFalse(is_allowed_path("/etc/passwd", ROOTS, is_write=False))

	def test_resolves_symlinks_before_deciding(self):
		with tempfile.TemporaryDirectory() as tmp:
			tmp = os.path.realpath(tmp)
			link = os.path.join(tmp, "escape")
			os.symlink("/etc/hosts", link)
			roots = {"read": (tmp,), "write": (), "config": frozenset()}
			self.assertFalse(is_allowed_path(link, roots, is_write=False))

	def test_config_files_refused_outside_config_modules(self):
		# The site directory is writable, but its config file holds the DB password.
		self.assertFalse(
			is_allowed_path("/frappe-bench/sites/test.local/site_config.json", ROOTS, is_write=False)
		)

	def test_synthetic_filenames_are_not_paths(self):
		for name in ("<unknown>", "<serverscript>", "<safe_eval>"):
			self.assertTrue(is_allowed_path(name, ROOTS, is_write=False))

	def test_is_inside(self):
		self.assertTrue(is_inside("/a/b", ("/a",)))
		self.assertTrue(is_inside("/a", ("/a",)))
		self.assertFalse(is_inside("/ab", ("/a",)))
		self.assertFalse(is_inside("/a", ()))

	def test_block_mode_end_to_end(self):
		result = subprocess.run(
			[sys.executable, "-c", BLOCK_MODE_SCRIPT],
			cwd=frappe.local.sites_path,
			env={**os.environ, "FRAPPE_AUDIT_HOOK_MODE": "block", "FRAPPE_STREAM_LOGGING": "1"},
			capture_output=True,
			text=True,
		)
		self.assertEqual(result.returncode, 0, msg=result.stderr)

		for name, passed in json.loads(result.stdout.strip().splitlines()[-1]).items():
			with self.subTest(name):
				self.assertTrue(passed)
