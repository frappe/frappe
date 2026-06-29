# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from typing import Any
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from flow.lib.resolver import schema_from_code
from flow.lib.tool import Tool, tool


class TestSchemaFromCode(UnitTestCase):
	def _props(self, code: str) -> dict[str, Any]:
		return schema_from_code(code)["properties"]

	def test_primitive_types(self):
		code = "def main(a: str, b: int, c: float, d: bool):\n\treturn 1\n"
		self.assertEqual(
			self._props(code),
			{
				"a": {"type": "string"},
				"b": {"type": "integer"},
				"c": {"type": "number"},
				"d": {"type": "boolean"},
			},
		)

	def test_unannotated_arg_has_no_constraint(self):
		self.assertEqual(self._props("def main(x):\n\treturn x\n"), {"x": {}})

	def test_list_of_strings(self):
		self.assertEqual(
			self._props("def main(tags: list[str]):\n\treturn tags\n"),
			{"tags": {"type": "array", "items": {"type": "string"}}},
		)

	def test_bare_list_and_dict(self):
		self.assertEqual(
			self._props("def main(a: list, b: dict):\n\treturn 1\n"),
			{"a": {"type": "array"}, "b": {"type": "object"}},
		)

	def test_literal_becomes_enum(self):
		code = 'def main(unit: Literal["celsius", "fahrenheit"]):\n\treturn unit\n'
		self.assertEqual(
			self._props(code),
			{"unit": {"enum": ["celsius", "fahrenheit"], "type": "string"}},
		)

	def test_optional_unwraps_to_inner_type(self):
		self.assertEqual(
			self._props("def main(name: Optional[str] = None):\n\treturn name\n"),
			{"name": {"type": "string"}},
		)

	def test_pep604_union_with_none_unwraps(self):
		self.assertEqual(
			self._props("def main(name: str | None = None):\n\treturn name\n"),
			{"name": {"type": "string"}},
		)

	def test_union_of_two_types_is_anyof(self):
		self.assertEqual(
			self._props("def main(x: int | str):\n\treturn x\n"),
			{"x": {"anyOf": [{"type": "integer"}, {"type": "string"}]}},
		)

	def test_annotated_attaches_description(self):
		code = 'def main(city: Annotated[str, "City name"]):\n\treturn city\n'
		self.assertEqual(
			self._props(code),
			{"city": {"type": "string", "description": "City name"}},
		)

	def test_unknown_type_falls_back_to_no_constraint(self):
		self.assertEqual(self._props("def main(x: SomeModel):\n\treturn x\n"), {"x": {}})

	def test_required_excludes_defaults(self):
		code = "def main(a: str, b: int = 3):\n\treturn 1\n"
		self.assertEqual(schema_from_code(code)["required"], ["a"])

	def test_no_required_key_when_all_optional(self):
		self.assertNotIn("required", schema_from_code("def main(a: str = 'x'):\n\treturn a\n"))

	def test_keyword_only_required(self):
		code = "def main(*, a: str, b: int = 1):\n\treturn 1\n"
		self.assertEqual(schema_from_code(code)["required"], ["a"])

	def test_additional_properties_false(self):
		self.assertFalse(schema_from_code("def main():\n\treturn 1\n")["additionalProperties"])


@tool
def _sample_weather(city: str) -> str:
	"""Sample weather tool."""
	return f"sunny in {city}"


def _plain_callable(city: str, days: int = 1) -> str:
	return city


SCRIPT_CODE = "def main(city: str):\n\treturn f'sunny in {city}'\n"


def _module_doc(**overrides: Any) -> dict:
	doc = {
		"doctype": "Flow Tool",
		"title": "Weather",
		"slug": "weather",
		"type": "Imported",
		"description": "Look up the weather.",
		"import_path": "flow.tools.builtins.weather",
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
		cls.enterClassContext(cls.enable_safe_exec())
		super().setUpClass()

	def tearDown(self):
		frappe.db.rollback()

	def test_module_tool_object_is_resolved(self):
		doc = frappe.get_doc(_module_doc()).insert()
		with patch("frappe.get_attr", return_value=_sample_weather):
			runtime = doc.to_tool()

		self.assertIsInstance(runtime, Tool)
		self.assertEqual(runtime.name, "weather")
		self.assertEqual(runtime.description, "Look up the weather.")
		self.assertEqual(runtime.parameters, _sample_weather.parameters)
		self.assertEqual(runtime(city="Paris"), "sunny in Paris")

	def test_module_plain_callable_schema_from_hints(self):
		doc = frappe.get_doc(_module_doc()).insert()
		with patch("frappe.get_attr", return_value=_plain_callable):
			runtime = doc.to_tool()

		self.assertEqual(runtime.parameters["properties"]["city"], {"type": "string"})
		self.assertEqual(runtime.parameters["properties"]["days"], {"type": "integer"})
		self.assertEqual(runtime.parameters["required"], ["city"])

	def test_module_import_failure_throws(self):
		doc = frappe.get_doc(_module_doc()).insert()
		with patch("frappe.get_attr", side_effect=ImportError("nope")):
			with self.assertRaisesRegex(frappe.ValidationError, "import"):
				doc.to_tool()

	def test_module_non_callable_throws(self):
		doc = frappe.get_doc(_module_doc()).insert()
		with patch("frappe.get_attr", return_value=42):
			with self.assertRaisesRegex(frappe.ValidationError, "not a Tool or callable"):
				doc.to_tool()

	def test_script_tool_executes_in_sandbox(self):
		doc = frappe.get_doc(_script_doc()).insert()
		runtime = doc.to_tool()

		self.assertEqual(runtime.name, "script_weather")
		self.assertEqual(runtime.parameters["properties"], {"city": {"type": "string"}})
		self.assertEqual(runtime(city="Paris"), "sunny in Paris")

	def test_script_tool_with_no_args_executes(self):
		doc = frappe.get_doc(
			_script_doc(slug="ping", title="Ping", code="def main():\n\treturn 'pong'\n")
		).insert()
		runtime = doc.to_tool()
		self.assertEqual(runtime(), "pong")
