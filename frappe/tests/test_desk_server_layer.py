# Code in frappe/ outside frappe/shell/ may not use the desk server. Today's breaks are the
# knownBreaks in frontend/architecture/layers.json, and that list may only shrink.

import ast
import json
import re
from pathlib import Path

import frappe
from frappe.tests import UnitTestCase

REPO = Path(frappe.__file__).parent.parent
LAYER_FILE = REPO / "frontend/architecture/layers.json"
SHELL = "frappe/shell/"
# The dotted paths in hooks.py name functions that the framework calls back; the desk server
# owns that contract. An import in hooks.py still counts.
CALLBACKS = {"frappe/hooks.py"}
TESTS = re.compile(r"(^|/)tests?/|(^|/)test_[^/]*\.py$")
IMPORTER = "frappe/utils/data.py"


class TestDeskServerLayer(UnitTestCase):
	def test_only_the_known_breaks_use_the_desk_server(self):
		known = known_breaks()
		uses = set(shell_uses())
		new = sorted(use for use in uses if not any(matches(k, use) for k in known))
		gone = sorted(k for k in known if not any(matches(k, use) for use in uses))
		self.assertFalse(new, f"These files use frappe.shell, which the framework server may not: {new}")
		self.assertFalse(gone, f"These breaks are gone; remove them from knownBreaks in layers.json: {gone}")

	def test_an_import_a_relative_import_and_a_dotted_path_each_count(self):
		for source in (
			"from frappe.shell.links import canonical_path",
			"import frappe.shell.links",
			"from ..shell import links",
			'frappe.get_attr("frappe.shell.links.canonical_path")',
			"from frappe.shell import links",
		):
			self.assertEqual(shell_targets(ast.parse(source), IMPORTER), {"frappe/shell/links.py"}, source)
		self.assertEqual(
			shell_targets(ast.parse("from frappe.shell import SHELL_ROOT"), IMPORTER),
			{"frappe/shell/__init__.py"},
		)
		self.assertEqual(shell_targets(ast.parse("from frappe.utils import cint"), IMPORTER), set())

	def test_a_hooks_callback_is_not_a_use_but_an_import_in_hooks_is(self):
		hooks = ast.parse(
			'before_app_install = "frappe.shell.install.before_app_install"\nimport frappe.shell.links'
		)
		self.assertEqual(shell_targets(hooks, "frappe/hooks.py", strings=False), {"frappe/shell/links.py"})


def known_breaks():
	breaks = json.loads(LAYER_FILE.read_text())["knownBreaks"]
	return [
		(b["from"], b["to"]) for b in breaks if not b["from"].startswith(SHELL) and b["to"].startswith(SHELL)
	]


def shell_uses():
	for path in (REPO / "frappe").rglob("*.py"):
		file = path.relative_to(REPO).as_posix()
		if file.startswith(SHELL) or TESTS.search(file):
			continue
		text = path.read_text()
		if "shell" in text:
			for target in shell_targets(ast.parse(text), file, strings=file not in CALLBACKS):
				yield (file, target)


# The desk server files a module reaches through imports and dotted-path strings.
def shell_targets(tree, file, strings=True):
	targets = set()
	for node in ast.walk(tree):
		if isinstance(node, ast.Import):
			dotted = [alias.name for alias in node.names]
		elif isinstance(node, ast.ImportFrom):
			base = absolute_module(node, file)
			dotted = [f"{base}.{alias.name}" for alias in node.names]
		elif strings and isinstance(node, ast.Constant) and isinstance(node.value, str):
			dotted = [node.value]
		else:
			continue
		for name in dotted:
			if name == "frappe.shell" or name.startswith("frappe.shell."):
				targets.add(shell_file(name))
	return targets - {None}


def absolute_module(node, file):
	if not node.level:
		return node.module or ""
	package = file.removesuffix(".py").split("/")[:-1]
	package = package[: len(package) - node.level + 1]
	return ".".join([*package, *([node.module] if node.module else [])])


# The longest prefix of a dotted name that is a module file: frappe.shell.links.x is links.py.
def shell_file(dotted):
	parts = dotted.split(".")
	for end in range(len(parts), 1, -1):
		for candidate in ("/".join(parts[:end]) + ".py", "/".join(parts[:end]) + "/__init__.py"):
			if (REPO / candidate).is_file():
				return candidate
	return None


def matches(known, use):
	return covers(known[0], use[0]) and covers(known[1], use[1])


# A path ending in "/" covers its folder; any other path covers only that file.
def covers(entry, file):
	return file.startswith(entry) if entry.endswith("/") else file == entry
