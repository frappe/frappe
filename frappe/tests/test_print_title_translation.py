# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import unittest
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


class TestPrintTitleTranslation(unittest.TestCase):
	def render_title(self, legacy, translations):
		# Render the shipped template without a database or an installed vertical app.
		env = Environment(loader=FileSystemLoader(Path(__file__).resolve().parents[1]), autoescape=True)
		env.globals.update(
			_=lambda text: translations.get(text, text),
			include_style=lambda name: "",
			include_script=lambda name: "",
		)
		return env.get_template("templates/print_format/print_format.html").render(
			legacy=legacy,
			doc={"doctype": "Example Table", "name": "Example Table-0001", "meta": {}},
			layout={"sections": []},
			print_format={},
		)

	def test_translates_doctype_but_not_document_name(self):
		for legacy in (False, True):
			with self.subTest(legacy=legacy):
				html = self.render_title(legacy, {"Example Table": "Restaurant Table"})
				self.assertIn("<title>Restaurant Table: Example Table-0001</title>", html)

	def test_untranslated_doctype_keeps_original_title(self):
		for legacy in (False, True):
			with self.subTest(legacy=legacy):
				self.assertIn(
					"<title>Example Table: Example Table-0001</title>", self.render_title(legacy, {})
				)


if __name__ == "__main__":
	unittest.main()
