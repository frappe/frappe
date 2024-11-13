from pathlib import Path
from unittest.mock import mock_open, patch

import frappe
from frappe.modules import patch_handler
from frappe.tests import IntegrationTestCase

EMTPY_FILE = ""
EMTPY_SECTION = """
[pre_model_sync]

[post_model_sync]
"""
FILLED_SECTIONS = """
[pre_model_sync]
app.module.patch1
app.module.patch2

[post_model_sync]
app.module.patch3

"""
OLD_STYLE_PATCH_TXT = """
app.module.patch1
app.module.patch2
app.module.patch3
"""

EDGE_CASES = """
[pre_model_sync]
App.module.patch1
app.module.patch2 # rerun
execute:frappe.db.updatedb("Item")
execute:frappe.function(arg="1")

[post_model_sync]
app.module.patch3
"""

COMMENTED_OUT = """
[pre_model_sync]
app.module.patch1
# app.module.patch2 # rerun
app.module.patch3

[post_model_sync]
app.module.patch4
"""


class TestPatches(IntegrationTestCase):
	def test_patch_module_names(self):
		frappe.flags.final_patches = []
		frappe.flags.in_install = True
		for patchmodule in patch_handler.get_all_patches():
			if patchmodule.startswith("execute:"):
				pass
			else:
				if patchmodule.startswith("finally:"):
					patchmodule = patchmodule.split("finally:")[-1]
				self.assertTrue(frappe.get_attr(patchmodule.split(maxsplit=1)[0] + ".execute"))

		frappe.flags.in_install = False

	def test_get_patch_list(self):
		pre = patch_handler.get_patches_from_app("frappe", patch_handler.PatchType.pre_model_sync)
		post = patch_handler.get_patches_from_app("frappe", patch_handler.PatchType.post_model_sync)
		all_patches = patch_handler.get_patches_from_app("frappe")
		self.assertGreater(len(pre), 0)
		self.assertGreater(len(post), 0)

		self.assertEqual(len(all_patches), len(pre) + len(post))

	def test_all_patches_are_marked_completed(self):
		all_patches = patch_handler.get_patches_from_app("frappe")
		finished_patches = frappe.db.count("Patch Log")

		self.assertGreaterEqual(finished_patches, len(all_patches))


class TestPatchReader(IntegrationTestCase):
	def get_patches(self):
		return (
			patch_handler.get_patches_from_app("frappe"),
			patch_handler.get_patches_from_app("frappe", patch_handler.PatchType.pre_model_sync),
			patch_handler.get_patches_from_app("frappe", patch_handler.PatchType.post_model_sync),
		)

	@patch("builtins.open", new_callable=mock_open, read_data=EMTPY_FILE)
	def test_empty_file(self, _file):
		all, pre, post = self.get_patches()
		self.assertEqual(all, [])
		self.assertEqual(pre, [])
		self.assertEqual(post, [])

	@patch("builtins.open", new_callable=mock_open, read_data=EMTPY_SECTION)
	def test_empty_sections(self, _file):
		all, pre, post = self.get_patches()
		self.assertEqual(all, [])
		self.assertEqual(pre, [])
		self.assertEqual(post, [])

	@patch("builtins.open", new_callable=mock_open, read_data=FILLED_SECTIONS)
	def test_new_style(self, _file):
		all, pre, post = self.get_patches()
		self.assertEqual(all, ["app.module.patch1", "app.module.patch2", "app.module.patch3"])
		self.assertEqual(pre, ["app.module.patch1", "app.module.patch2"])
		self.assertEqual(
			post,
			[
				"app.module.patch3",
			],
		)

	@patch("builtins.open", new_callable=mock_open, read_data=OLD_STYLE_PATCH_TXT)
	def test_old_style(self, _file):
		all, pre, post = self.get_patches()
		self.assertEqual(all, ["app.module.patch1", "app.module.patch2", "app.module.patch3"])
		self.assertEqual(pre, ["app.module.patch1", "app.module.patch2", "app.module.patch3"])
		self.assertEqual(post, [])

	@patch("builtins.open", new_callable=mock_open, read_data=EDGE_CASES)
	def test_new_style_edge_cases(self, _file):
		all, pre, post = self.get_patches()
		self.assertEqual(
			pre,
			[
				"App.module.patch1",
				"app.module.patch2 # rerun",
				'execute:frappe.db.updatedb("Item")',
				'execute:frappe.function(arg="1")',
			],
		)

	@patch("builtins.open", new_callable=mock_open, read_data=COMMENTED_OUT)
	def test_ignore_comments(self, _file):
		all, pre, post = self.get_patches()
		self.assertEqual(pre, ["app.module.patch1", "app.module.patch3"])

	def test_verify_patch_txt(self):
		"""Make sure all patches/**.py files are part of patches.txt"""
		check_patch_files("frappe")


# Do not remove/rename this function, other apps depend on it to test their patches
def check_patch_files(app):
	"""Make sure all patches/**.py files are part of patches.txt"""

	patch_dir = Path(frappe.get_app_path(app)) / "patches"

	app_patches = [p.split(maxsplit=1)[0] for p in patch_handler.get_patches_from_app(app)]

	missing_patches = []

	for file in patch_dir.glob("**/*.py"):
		module = _get_dotted_path(file, app)
		try:
			patch_module = frappe.get_module(module)
			if hasattr(patch_module, "execute"):
				if module not in app_patches:
					missing_patches.append(module)
		except Exception:
			# patch so bad it doesn't even import :shrug:
			missing_patches.append(module)

	if missing_patches:
		raise Exception("Patches missing in patch.txt: \n" + "\n".join(missing_patches))


def _get_dotted_path(file: Path, app) -> str:
	app_path = Path(frappe.get_app_path(app))

	*path, filename = file.relative_to(app_path).parts
	base_filename = Path(filename).stem

	return ".".join([app, *path, base_filename])
