import os
import re

import frappe
from frappe.studio.api import get_component_definition
from frappe.studio.components import get_schema_files
from frappe.tests import IntegrationTestCase

EDITOR_COMPONENT_FILES = ("components.ts", "componentFamilies.ts")


class TestComponents(IntegrationTestCase):
	def test_definition_is_the_schema_of_the_props(self):
		props = get_component_definition("Repeater")["definitions"]["RepeaterProps"]

		self.assertEqual(props["required"], ["dataKey"])
		self.assertEqual(props["properties"]["data"]["type"], "array")

	def test_every_schema_file_has_a_definition(self):
		for component in get_schema_files():
			self.assertTrue(get_component_definition(component)["definitions"], component)

	def test_unknown_component_is_rejected(self):
		self.assertRaises(frappe.ValidationError, get_component_definition, "NoSuchComponent")
		self.assertRaises(frappe.ValidationError, get_component_definition, "../package")
		with self.assertRaisesRegex(frappe.ValidationError, "&lt;img&gt;"):
			get_component_definition("<img>")

	def test_skill_reference_names_every_built_in_component(self):
		reference = read_source_file("skills", "studio-app-building", "BUILT_IN_COMPONENTS.md")
		for file_name in EDITOR_COMPONENT_FILES:
			source = read_source_file("studio", "frontend", "src", "data", file_name)
			for component in re.findall(r'^\t\tname: "(\w+)"', source, re.MULTILINE):
				self.assertIn(
					f"`{component}`", reference, f"{component} is missing from BUILT_IN_COMPONENTS.md"
				)


def read_source_file(*parts: str) -> str:
	with open(os.path.join(frappe.get_app_source_path("frappe"), *parts), encoding="utf-8") as source_file:
		return source_file.read()
