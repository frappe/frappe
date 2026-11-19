# Only client_script.py may run the template compiler in frontend/templateCompiler/. The JS layer
# check in frontend/architecture/ cannot see a Python `node` call, so this test checks it.

from pathlib import Path

import frappe
from frappe.tests import UnitTestCase

REPO = Path(frappe.__file__).parent.parent
COMPILER = "templateCompiler"
USERS = {
	"frappe/custom/doctype/client_script/client_script.py",
	"frappe/tests/test_template_compiler_users.py",
}


class TestTemplateCompilerUsers(UnitTestCase):
	def test_only_client_script_names_the_template_compiler(self):
		others = sorted(file for file in files_naming_the_compiler() if file not in USERS)
		self.assertFalse(others, f"Only client_script.py may run frontend/templateCompiler: {others}")

	def test_client_script_still_names_it(self):
		self.assertIn(
			"frappe/custom/doctype/client_script/client_script.py", set(files_naming_the_compiler())
		)


def files_naming_the_compiler():
	for path in (REPO / "frappe").rglob("*.py"):
		if COMPILER in path.read_text():
			yield path.relative_to(REPO).as_posix()
