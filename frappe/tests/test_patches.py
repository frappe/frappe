from __future__ import unicode_literals

import unittest

import frappe
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
					patchmodule = patchmodule.split("finally:")[-1]
				self.assertTrue(frappe.get_attr(patchmodule.split()[0] + ".execute"))

		frappe.flags.in_install = False
