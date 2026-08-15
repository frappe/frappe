from enum import Enum
from typing import Annotated, Literal

import pytest
from pydantic import BaseModel, ValidationError

from flow.tools.tool import Tool, ToolContext, build_schema, tool


def test_primitives_and_required():
	def f(a: int, b: str, c: bool = False):
		pass

	schema = build_schema(f)
	assert schema["properties"]["a"] == {"type": "integer"}
	assert schema["properties"]["b"] == {"type": "string"}
	assert schema["properties"]["c"] == {"type": "boolean"}
	assert schema["required"] == ["a", "b"]  # c has a default
	assert schema["additionalProperties"] is False


def test_annotated_description():
	def f(x: Annotated[int, "the line number"]):
		pass

	prop = build_schema(f)["properties"]["x"]
	assert prop == {"type": "integer", "description": "the line number"}


def test_optional_unwraps_and_not_required():
	def f(x: int | None):
		pass

	schema = build_schema(f)
	assert schema["properties"]["x"] == {"type": "integer"}
	assert "required" not in schema


def test_literal_becomes_enum():
	def f(mode: Literal["r", "w"]):
		pass

	assert build_schema(f)["properties"]["mode"] == {"type": "string", "enum": ["r", "w"]}


def test_list_items_typed():
	def f(xs: list[int]):
		pass

	assert build_schema(f)["properties"]["xs"] == {"type": "array", "items": {"type": "integer"}}


def test_union_anyof():
	def f(x: int | str):
		pass

	assert build_schema(f)["properties"]["x"] == {"anyOf": [{"type": "integer"}, {"type": "string"}]}


def test_pydantic_model_inlined():
	class Point(BaseModel):
		x: int
		y: int

	def f(p: Point):
		pass

	prop = build_schema(f)["properties"]["p"]
	assert prop["type"] == "object"
	assert prop["properties"]["x"]["type"] == "integer"


def test_enum_values():
	class Color(Enum):
		RED = "red"
		BLUE = "blue"

	def f(c: Color):
		pass

	assert build_schema(f)["properties"]["c"] == {"type": "string", "enum": ["red", "blue"]}


def test_ctx_and_varargs_skipped():
	def f(a: int, *args, ctx: ToolContext, **kwargs):
		pass

	assert list(build_schema(f)["properties"]) == ["a"]


# --- @tool decorator + Tool --------------------------------------------------


def test_tool_decorator_derives_name_and_description():
	@tool
	async def do_thing(x: int, *, ctx: ToolContext) -> str:
		"""Does a thing."""
		return str(x)

	assert isinstance(do_thing, Tool)
	assert do_thing.name == "do_thing"
	assert do_thing.description == "Does a thing."
	assert do_thing.parameters["properties"]["x"] == {"type": "integer"}
	assert do_thing.requires_confirmation is False


def test_tool_decorator_overrides_and_confirmation():
	@tool(
		name="custom",
		description="d",
		requires_confirmation=True,
		display="Running custom tool",
	)
	async def _f(*, ctx: ToolContext) -> str:
		return "ok"

	assert _f.name == "custom"
	assert _f.description == "d"
	assert _f.requires_confirmation is True
	assert _f.display == "Running custom tool"


def test_tool_display_accepts_argument_placeholders_but_rejects_unknown_arguments():
	@tool(display="Searching the web for {{ query }}")
	async def web_search(query: str, *, ctx: ToolContext) -> str:
		return query

	assert web_search.display == "Searching the web for {{ query }}"
	assert "display" not in web_search.to_schema()
	assert "display" not in web_search.to_schema()["function"]

	with pytest.raises(ValueError, match=r"unknown argument.*missing"):

		@tool(display="Searching for {{ missing }}")
		async def invalid(query: str, *, ctx: ToolContext) -> str:
			return query


def test_tool_to_schema_shape():
	@tool
	async def sample(x: int, *, ctx: ToolContext) -> str:
		"""S."""
		return str(x)

	schema = sample.to_schema()
	assert schema["type"] == "function"
	assert schema["function"]["name"] == "sample"
	assert schema["function"]["parameters"]["properties"]["x"] == {"type": "integer"}


async def test_tool_call_coerces_arguments():
	@tool
	async def sample(x: int, y: str = "d", *, ctx: ToolContext) -> str:
		return f"{x}{y}"

	# model sends "5" as a string; validate_call coerces to int
	assert await sample(x="5", ctx=ToolContext()) == "5d"


async def test_tool_call_rejects_bad_arguments():
	@tool
	async def sample(x: int, *, ctx: ToolContext) -> str:
		return str(x)

	with pytest.raises(ValidationError):
		await sample(x="not-an-int", ctx=ToolContext())
