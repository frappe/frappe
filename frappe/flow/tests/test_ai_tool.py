# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from enum import Enum
from typing import Annotated, Literal

from frappe.tests import UnitTestCase
from pydantic import BaseModel, Field, ValidationError

from flow.lib.tool import Tool, build_schema, tool


class TestToolDecorator(UnitTestCase):
	def test_bare_decorator_uses_name_and_docstring(self):
		@tool
		def get_weather(city: str) -> str:
			"""Return the current weather for a city."""
			return f"sunny in {city}"

		self.assertIsInstance(get_weather, Tool)
		self.assertEqual(get_weather.name, "get_weather")
		self.assertEqual(get_weather.description, "Return the current weather for a city.")

	def test_parameterized_decorator_overrides_name_and_description(self):
		@tool(name="weather", description="Look up weather.")
		def get_weather(city: str) -> str:
			"""ignored docstring"""
			return f"sunny in {city}"

		self.assertEqual(get_weather.name, "weather")
		self.assertEqual(get_weather.description, "Look up weather.")

	def test_calling_tool_invokes_wrapped_function(self):
		@tool
		def add(a: int, b: int) -> int:
			"""Add two integers."""
			return a + b

		self.assertEqual(add(a=2, b=3), 5)

	def test_call_validates_and_coerces_types(self):
		@tool
		def add(a: int, b: int) -> int:
			"""Add two integers."""
			return a + b

		self.assertEqual(add(a="2", b="3"), 5)

	def test_call_rejects_invalid_arguments(self):
		@tool
		def add(a: int, b: int) -> int:
			"""Add two integers."""
			return a + b

		with self.assertRaises(ValidationError):
			add(a="not a number", b=3)

	def test_to_dict_returns_function_envelope(self):
		@tool
		def ping() -> str:
			"""Ping."""
			return "pong"

		schema = ping.to_dict()
		self.assertEqual(schema["type"], "function")
		self.assertEqual(schema["function"]["name"], "ping")
		self.assertEqual(schema["function"]["description"], "Ping.")
		self.assertIn("parameters", schema["function"])


class TestSchemaPrimitives(UnitTestCase):
	def test_primitives_and_required_flag(self):
		def f(s: str, i: int, x: float, b: bool):
			pass

		schema = build_schema(f)
		self.assertEqual(
			schema["properties"],
			{
				"s": {"type": "string"},
				"i": {"type": "integer"},
				"x": {"type": "number"},
				"b": {"type": "boolean"},
			},
		)
		self.assertEqual(set(schema["required"]), {"s", "i", "x", "b"})
		self.assertFalse(schema["additionalProperties"])

	def test_default_value_makes_argument_optional(self):
		def f(city: str, units: str = "metric"):
			pass

		schema = build_schema(f)
		self.assertEqual(schema["required"], ["city"])

	def test_optional_type_makes_argument_optional(self):
		def f(city: str, note: str | None = None):
			pass

		schema = build_schema(f)
		self.assertEqual(schema["required"], ["city"])
		self.assertEqual(schema["properties"]["note"], {"type": "string"})

	def test_pipe_optional_syntax(self):
		def f(city: str | None = None):
			pass

		schema = build_schema(f)
		self.assertNotIn("required", schema)
		self.assertEqual(schema["properties"]["city"], {"type": "string"})

	def test_list_of_primitive(self):
		def f(tags: list[str]):
			pass

		schema = build_schema(f)
		self.assertEqual(
			schema["properties"]["tags"],
			{"type": "array", "items": {"type": "string"}},
		)

	def test_set_and_tuple_become_arrays(self):
		def f(s: set[str], t: tuple[int, ...]):
			pass

		schema = build_schema(f)
		self.assertEqual(schema["properties"]["s"]["type"], "array")
		self.assertEqual(schema["properties"]["s"]["items"], {"type": "string"})
		self.assertEqual(schema["properties"]["t"]["type"], "array")
		self.assertEqual(schema["properties"]["t"]["items"], {"type": "integer"})

	def test_dict_treated_as_object(self):
		def f(metadata: dict):
			pass

		schema = build_schema(f)
		self.assertEqual(schema["properties"]["metadata"], {"type": "object"})

	def test_literal_becomes_string_enum(self):
		def f(units: Literal["metric", "imperial"]):
			pass

		schema = build_schema(f)
		self.assertEqual(
			schema["properties"]["units"],
			{"type": "string", "enum": ["metric", "imperial"]},
		)

	def test_int_enum_class(self):
		class Priority(Enum):
			LOW = 1
			HIGH = 2

		def f(p: Priority):
			pass

		schema = build_schema(f)
		self.assertEqual(
			schema["properties"]["p"],
			{"type": "integer", "enum": [1, 2]},
		)

	def test_annotated_provides_description(self):
		def f(city: Annotated[str, "The city name, e.g. 'Mumbai'"]):
			pass

		schema = build_schema(f)
		self.assertEqual(
			schema["properties"]["city"],
			{"type": "string", "description": "The city name, e.g. 'Mumbai'"},
		)

	def test_annotated_optional_combines(self):
		def f(note: Annotated[str | None, "An optional note"] = None):
			pass

		schema = build_schema(f)
		self.assertEqual(
			schema["properties"]["note"],
			{"type": "string", "description": "An optional note"},
		)
		self.assertNotIn("required", schema)

	def test_pydantic_model_uses_model_schema(self):
		class Address(BaseModel):
			street: str
			city: str = Field(..., description="The city")

		def f(addr: Address):
			pass

		schema = build_schema(f)
		addr_schema = schema["properties"]["addr"]
		self.assertEqual(addr_schema["type"], "object")
		self.assertIn("street", addr_schema["properties"])
		self.assertIn("city", addr_schema["properties"])

	def test_nested_pydantic_model_inlines_refs(self):
		class Inner(BaseModel):
			x: int

		class Outer(BaseModel):
			inner: Inner

		def f(outer: Outer):
			pass

		schema = build_schema(f)
		outer_schema = schema["properties"]["outer"]
		self.assertNotIn("$defs", outer_schema)
		inner_schema = outer_schema["properties"]["inner"]
		self.assertNotIn("$ref", inner_schema)
		self.assertEqual(inner_schema["type"], "object")
		self.assertIn("x", inner_schema["properties"])

	def test_var_args_and_kwargs_are_skipped(self):
		def f(x: int, *args, **kwargs):
			pass

		schema = build_schema(f)
		self.assertEqual(list(schema["properties"].keys()), ["x"])

	def test_no_parameters(self):
		def f():
			pass

		schema = build_schema(f)
		self.assertEqual(schema["properties"], {})
		self.assertNotIn("required", schema)
		self.assertFalse(schema["additionalProperties"])
