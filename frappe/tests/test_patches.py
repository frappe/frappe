
import unittest, frappe
from frappe.modules import patch_handler

class TestPatches(unittest.TestCase):
	def test_patch_module_names(self):
		frappe.flags.final_patches = []
		frappe.flags.in_install = True
		for patchmodule in patch_handler.get_all_patches():
			if patchmodule.startswith("execute:"):
				pass
			else:
				if patchmodule.startswith("finally:"):
					patchmodule = patchmodule.split('finally:')[-1]
				self.assertTrue(frappe.get_attr(patchmodule.split()[0] + ".execute"))

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
