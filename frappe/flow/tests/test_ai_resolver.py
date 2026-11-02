# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from typing import Any
from unittest.mock import patch

import frappe
from frappe.flow.lib.resolver import schema_from_code
from frappe.flow.lib.tool import Tool, ToolContext, tool
from frappe.tests import IntegrationTestCase, UnitTestCase


class TestSchemaFromCode(UnitTestCase):
	def test_each_annotation_maps_to_its_json_schema(self):
		for annotation, expected in (
			("str", {"type": "string"}),
			("int", {"type": "integer"}),
			("float", {"type": "number"}),
			("bool", {"type": "boolean"}),
			(None, {}),
			("list[str]", {"type": "array", "items": {"type": "string"}}),
			("list", {"type": "array"}),
			("dict", {"type": "object"}),
			('Literal["celsius", "fahrenheit"]', {"enum": ["celsius", "fahrenheit"], "type": "string"}),
			("Optional[str]", {"type": "string"}),
			("str | None", {"type": "string"}),
			("int | str", {"anyOf": [{"type": "integer"}, {"type": "string"}]}),
			('Annotated[str, "City name"]', {"type": "string", "description": "City name"}),
			("SomeModel", {}),
		):
			arg = f"x: {annotation}" if annotation else "x"
			with self.subTest(annotation=annotation):
				self.assertEqual(
					schema_from_code(f"def main({arg}):\n\treturn x\n")["properties"], {"x": expected}
				)

	def test_required_lists_the_arguments_without_defaults(self):
		for signature, required in (("a: str, b: int = 3", ["a"]), ("*, a: str, b: int = 1", ["a"])):
			with self.subTest(signature=signature):
				self.assertEqual(
					schema_from_code(f"def main({signature}):\n\treturn 1\n")["required"], required
				)
		schema = schema_from_code("def main(a: str = 'x'):\n\treturn a\n")
		self.assertNotIn("required", schema)
		self.assertFalse(schema["additionalProperties"])


@tool(display_template="Checking the weather in {{ city }}")
def _templated_weather(city: str, *, ctx: ToolContext) -> str:
	"""Sample weather tool with a display template."""
	return f"sunny in {city}"


def _plain_callable(city: str, days: int = 1, *, ctx: ToolContext) -> str:
	return city


SCRIPT_CODE = "def main(city: str):\n\treturn f'sunny in {city}'\n"
CTX = ToolContext(session_id="test", agent="Test Agent", user="Administrator")


def _module_doc(**overrides: Any) -> dict:
	doc = {
		"doctype": "Flow Tool",
		"title": "Weather",
		"slug": "weather",
		"type": "Imported",
		"description": "Look up the weather.",
		"import_path": "frappe.flow.tools.builtins.weather",
	}
	doc.update(overrides)
	return doc


def _script_doc(**overrides: Any) -> dict:
	doc = {
		"doctype": "Flow Tool",
		"title": "Script Weather",
		"slug": "script_weather",
		"type": "Script",
		"description": "Look up the weather.",
		"code": SCRIPT_CODE,
	}
	doc.update(overrides)
	return doc


class TestResolveTool(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		cls.enterClassContext(patch("frappe.utils.safe_exec.is_safe_exec_enabled", return_value=True))
		super().setUpClass()

	def tearDown(self):
		frappe.db.rollback()

	def test_an_imported_tool_resolves_from_its_import_path(self):
		doc = frappe.get_doc(_module_doc(background=1)).insert()
		with self.subTest("a Tool object"):
			with patch("frappe.get_attr", return_value=_templated_weather):
				runtime = doc.to_tool()
			self.assertIsInstance(runtime, Tool)
			self.assertEqual((runtime.name, runtime.description), ("weather", "Look up the weather."))
			self.assertEqual(runtime.parameters, _templated_weather.parameters)
			self.assertEqual(runtime.to_dict()["display_template"], "Checking the weather in {{ city }}")
			self.assertEqual(runtime(city="Paris", ctx=CTX), "sunny in Paris")

		with self.subTest("a plain callable"):
			with patch("frappe.get_attr", return_value=_plain_callable):
				runtime = doc.to_tool()
			self.assertEqual(
				runtime.parameters["properties"], {"city": {"type": "string"}, "days": {"type": "integer"}}
			)
			self.assertEqual(runtime.parameters["required"], ["city"])
			self.assertTrue(runtime.background)

		for label, attr, error in (
			("a failed import", {"side_effect": ImportError("nope")}, "import"),
			("not callable", {"return_value": 42}, "not a Tool or callable"),
		):
			with (
				self.subTest(label),
				patch("frappe.get_attr", **attr),
				self.assertRaisesRegex(frappe.ValidationError, error),
			):
				doc.to_tool()

	def test_a_script_tool_runs_main_in_the_sandbox(self):
		runtime = frappe.get_doc(_script_doc()).insert().to_tool()
		self.assertEqual(runtime.name, "script_weather")
		self.assertEqual(runtime.parameters["properties"], {"city": {"type": "string"}})
		self.assertEqual(runtime(city="Paris", ctx=CTX), "sunny in Paris")

		ping = frappe.get_doc(_script_doc(slug="ping", title="Ping", code="def main():\n\treturn 'pong'\n"))
		self.assertEqual(ping.insert().to_tool()(ctx=CTX), "pong")
