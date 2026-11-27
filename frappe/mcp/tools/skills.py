# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Read the Flow Skills open to the user through Frappe's skill API."""

from pydantic import Field

from frappe.api import skills
from frappe.mcp.tools import Tool, ToolArguments


class ListSkillsArguments(ToolArguments):
	pass


class GetSkillArguments(ToolArguments):
	name: str = Field(min_length=1)
	file: str | None = None


LIST_SKILLS = Tool(
	name="list_skills",
	description="List the skills you can load, each with a description of when it applies.",
	arguments=ListSkillsArguments,
	handler=skills.list_skills,
	annotations={"readOnlyHint": True},
)

GET_SKILL = Tool(
	name="get_skill",
	description=(
		"Load a skill's full instructions by name, then follow them. When a task matches a skill, "
		"call this with that exact name before starting the task, and treat what you get back as "
		"authoritative for it. When the instructions mention a file, such as references/forms.md, "
		"call this again with the same name and that path as `file` to read it; a folder path lists "
		"the files in it."
	),
	arguments=GetSkillArguments,
	handler=skills.get_skill,
	annotations={"readOnlyHint": True},
)
