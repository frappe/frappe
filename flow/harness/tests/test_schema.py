from enum import Enum
from typing import Annotated, Literal

import pytest
from pydantic import BaseModel, ValidationError

from flow_harness.events import DisplaySegment
from flow_harness.tools.tool import Tool, ToolContext, build_schema, render_tool_display, tool


def test_build_schema_maps_python_annotations():
	class Point(BaseModel):
		x: int
		y: int

	class Color(Enum):
		RED = "red"
		BLUE = "blue"

	def f(
		a: int,
		b: str,
		line: Annotated[int, "the line number"],
		mode: Literal["r", "w"],
		xs: list[int],
		either: int | str,
		p: Point,
		c: Color,
		maybe: int | None,
		flag: bool = False,
		*args,
		ctx: ToolContext,
		**kwargs,
	):
		pass

	schema = build_schema(f)
	properties = schema["properties"]
	point = properties.pop("p")
	assert point["type"] == "object"  # a pydantic model is inlined
	assert point["properties"]["x"]["type"] == "integer"
	assert properties == {  # ctx and varargs are skipped
		"a": {"type": "integer"},
		"b": {"type": "string"},
		"line": {"type": "integer", "description": "the line number"},
		"mode": {"type": "string", "enum": ["r", "w"]},
		"xs": {"type": "array", "items": {"type": "integer"}},
		"either": {"anyOf": [{"type": "integer"}, {"type": "string"}]},
		"c": {"type": "string", "enum": ["red", "blue"]},
		"maybe": {"type": "integer"},  # Optional unwraps
		"flag": {"type": "boolean"},
	}
	# required: no default and not Optional
	assert schema["required"] == ["a", "b", "line", "mode", "xs", "either", "p", "c"]
	assert schema["additionalProperties"] is False

	def g(x: int | None):
		pass

	assert "required" not in build_schema(g)


async def test_tool_decorator_builds_a_validated_tool():
	@tool
	async def sample(x: int, y: str = "d", *, ctx: ToolContext) -> str:
		"""Does a thing."""
		return f"{x}{y}"

	assert isinstance(sample, Tool)
	assert (sample.name, sample.description) == ("sample", "Does a thing.")
	assert sample.requires_confirmation is False
	schema = sample.to_schema()
	assert (schema["type"], schema["function"]["name"]) == ("function", "sample")
	assert schema["function"]["parameters"]["properties"]["x"] == {"type": "integer"}
	# the model sends "5" as a string; validation coerces it to int
	assert await sample(x="5", ctx=ToolContext()) == "5d"
	with pytest.raises(ValidationError):
		await sample(x="not-an-int", ctx=ToolContext())

	@tool(name="custom", description="d", requires_confirmation=True, display_template="Running custom tool")
	async def _f(*, ctx: ToolContext) -> str:
		return "ok"

	assert (_f.name, _f.description, _f.requires_confirmation) == ("custom", "d", True)
	assert _f.display_template == "Running custom tool"


def test_tool_display_template_takes_only_known_arguments():
	@tool(display_template="Searching the web for {{ query }}")
	async def web_search(query: str, *, ctx: ToolContext) -> str:
		return query

	assert web_search.display_template == "Searching the web for {{ query }}"
	assert "display_template" not in web_search.to_schema()
	assert "display_template" not in web_search.to_schema()["function"]

	with pytest.raises(ValueError, match=r"unknown argument.*missing"):

		@tool(display_template="Searching for {{ missing }}")
		async def invalid(query: str, *, ctx: ToolContext) -> str:
			return query

	segments = render_tool_display("Reading file {{ path }}", {"path": "docs/architecture.md"})
	assert segments == [
		DisplaySegment(text="Reading file "),
		DisplaySegment(text="docs/architecture.md", arg="path"),
	]
	with pytest.raises(ValueError, match="placeholders"):
		render_tool_display("Reading {{ path | basename }}", {"path": "a.md"})
