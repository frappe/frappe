# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, ValidationError

from frappe.flow.lib.tool import Tool, ToolContext, build_schema, tool
from frappe.tests import UnitTestCase

CTX = ToolContext(session_id="test", agent="Test Agent", user="Administrator")


class TestToolDecorator(UnitTestCase):
	def test_a_decorated_function_becomes_a_tool_with_its_schema(self):
		@tool
		def get_weather(city: str, *, ctx: ToolContext) -> str:
			"""Return the current weather for a city."""
			return f"sunny in {city}"

		@tool(name="weather", description="Look up weather.", display_template="Weather in {{ city }}")
		def named(city: str, *, ctx: ToolContext) -> str:
			"""ignored docstring"""
			return city

		self.assertIsInstance(get_weather, Tool)
		# ctx is not in the model's schema
		self.assertEqual(get_weather.parameters["properties"], {"city": {"type": "string"}})
		self.assertEqual(
			get_weather.to_dict(),
			{
				"type": "function",
				"function": {
					"name": "get_weather",
					"description": "Return the current weather for a city.",
					"parameters": get_weather.parameters,
				},
			},
		)
		self.assertEqual((named.name, named.description), ("weather", "Look up weather."))
		self.assertEqual(named.to_dict()["display_template"], "Weather in {{ city }}")

	def test_a_call_validates_its_arguments_and_passes_the_context(self):
		@tool
		def add(a: int, b: int, *, ctx: ToolContext) -> tuple[int, str]:
			"""Add two integers."""
			return a + b, ctx.session_id

		self.assertEqual(add(a=2, b=3, ctx=CTX), (5, "test"))
		self.assertEqual(add(a="2", b="3", ctx=CTX), (5, "test"))
		with self.assertRaises(ValidationError):
			add(a="not a number", b=3, ctx=CTX)

	def test_a_bad_definition_is_refused(self):
		with self.assertRaisesRegex(ValueError, r"unknown argument\(s\): name"):

			@tool(display_template="Reading {{ name }}")
			def read(doctype: str, *, ctx: ToolContext) -> str:
				return doctype

		with self.assertRaisesRegex(TypeError, r"Tool ping must take `\*, ctx: ToolContext`"):

			@tool
			def ping() -> str:
				"""Ping."""
				return "pong"


class TestSchemaPrimitives(UnitTestCase):
	def test_each_hint_maps_to_its_json_schema(self):
		class Priority(Enum):
			LOW = 1
			HIGH = 2

		class Address(BaseModel):
			street: str
			city: str = Field(..., description="The city")

		class Inner(BaseModel):
			x: int

		class Outer(BaseModel):
			inner: Inner

		def f(
			s: str,
			i: int,
			x: float,
			b: bool,
			tags: list[str],
			unique: set[str],
			pair: tuple[int, ...],
			metadata: dict,
			units: Literal["metric", "imperial"],
			p: Priority,
			city: Annotated[str, "The city name, e.g. 'Mumbai'"],
			addr: Address,
			outer: Outer,
			note: Annotated[str | None, "An optional note"] = None,
		):
			pass

		properties = build_schema(f)["properties"]
		addr, outer = properties.pop("addr"), properties.pop("outer")
		self.assertEqual(
			properties,
			{
				"s": {"type": "string"},
				"i": {"type": "integer"},
				"x": {"type": "number"},
				"b": {"type": "boolean"},
				"tags": {"type": "array", "items": {"type": "string"}},
				"unique": {"type": "array", "items": {"type": "string"}},
				"pair": {"type": "array", "items": {"type": "integer"}},
				"metadata": {"type": "object"},
				"units": {"type": "string", "enum": ["metric", "imperial"]},
				"p": {"type": "integer", "enum": [1, 2]},
				"city": {"type": "string", "description": "The city name, e.g. 'Mumbai'"},
				"note": {"type": "string", "description": "An optional note"},
			},
		)
		# a pydantic model's own schema, with nested refs inlined
		self.assertEqual(addr["type"], "object")
		self.assertIn("street", addr["properties"])
		self.assertIn("city", addr["properties"])
		self.assertNotIn("$defs", outer)
		inner = outer["properties"]["inner"]
		self.assertNotIn("$ref", inner)
		self.assertEqual(inner["type"], "object")
		self.assertIn("x", inner["properties"])

	def test_arguments_without_a_default_or_none_are_required(self):
		def f(city: str, units: str = "metric", note: str | None = None, *args, **kwargs):
			pass

		def g():
			pass

		self.assertEqual(
			build_schema(f),
			{
				"type": "object",
				"properties": {
					"city": {"type": "string"},
					"units": {"type": "string"},
					"note": {"type": "string"},
				},
				"additionalProperties": False,
				"required": ["city"],
			},
		)
		self.assertEqual(build_schema(g), {"type": "object", "properties": {}, "additionalProperties": False})
