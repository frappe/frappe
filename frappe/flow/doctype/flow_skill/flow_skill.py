# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import re
from html import escape

import frappe
from frappe import _
from frappe.model.document import Document

from flow.utils.system_generated import block_delete, block_rename, validate_immutable

MAX_DESCRIPTION_LENGTH = 1024

# A global skill lands in every agent's prompt, so it is capped tighter than a bound one.
MAX_GLOBAL_SKILLS = 10

_SKILL_COMMAND_RE = re.compile(r"/skill:(\S+)(?:\s+(.*))?$", re.DOTALL)
# a "/skill:<command>" word anywhere in a message
_SKILL_TOKEN_RE = re.compile(r"(?<!\S)/skill:(\S+)")

# Rides inside the wrapper, unseen by the user: the agent's index still says to load skills.
SKILL_LOADED_NOTE = "This is the full skill, already loaded. Follow it; do not call load_skill for it."


class FlowSkill(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		description: DF.SmallText
		enabled: DF.Check
		instructions: DF.LongText
		is_global: DF.Check
		is_system_generated: DF.Check
		title: DF.Data
		user_invocable: DF.Check
	# end: auto-generated types

	def validate(self):
		self._validate_description()
		self._validate_global_limit()
		self._validate_command()
		validate_immutable(self, ("description", "instructions"))

	def on_trash(self):
		block_delete(self)

	def before_rename(self, old: str, new: str, merge: bool = False) -> None:
		block_rename(self, old)

	def _validate_description(self):
		"""Every bound skill's description rides in the agent's prompt, so keep it short."""
		if len(self.description or "") > MAX_DESCRIPTION_LENGTH:
			frappe.throw(
				_("Description must be at most {0} characters.").format(MAX_DESCRIPTION_LENGTH),
				title=_("Description Too Long"),
			)

	def _validate_command(self):
		"""A user-invocable skill answers to /skill:<command>, so its command must be typable and its own."""
		if not self.user_invocable:
			return
		command = skill_command(self.title or "")
		if not command:
			frappe.throw(
				_("A user-invocable skill needs a letter or digit in its title."), title=_("Invalid Title")
			)
		for other in frappe.get_all(
			"Flow Skill", filters={"user_invocable": 1, "name": ["!=", self.name or ""]}, pluck="name"
		):
			if skill_command(other) == command:
				frappe.throw(
					_("{0} already answers to /skill:{1}. Choose a different name.").format(other, command),
					title=_("Duplicate Skill Command"),
				)

	def _validate_global_limit(self):
		if not (self.is_global and self.enabled):
			return
		others = frappe.db.count(
			"Flow Skill", {"is_global": 1, "enabled": 1, "name": ["!=", self.name or ""]}
		)
		if others >= MAX_GLOBAL_SKILLS:
			frappe.throw(
				_("At most {0} skills can be available to all agents.").format(MAX_GLOBAL_SKILLS),
				title=_("Too Many Global Skills"),
			)


def expand_skill_command(agent: str, text: str) -> str:
	"""Put the instructions of each skill named with `/skill:<command>` before the message."""
	stripped = text.strip()
	leading = _SKILL_COMMAND_RE.match(stripped)
	instructions = (leading.group(2) or "").strip() if leading else stripped
	# skip quoted lines
	later = [
		command
		for line in instructions.split("\n")
		if not line.startswith(">")
		for command in _SKILL_TOKEN_RE.findall(line)
	]
	# named again later: keep the text as typed, leading command included
	if leading and leading.group(1) in later:
		instructions = stripped
	commands = ([leading.group(1)] if leading else []) + later
	if not commands:
		return text
	skills: dict[str, dict] = {}
	for row in frappe.get_doc("Flow Agent", agent).invocable_skills():
		skills.setdefault(row["command"], row)
	if leading and leading.group(1) not in skills:
		frappe.throw(
			_("No skill named {0}. Available: {1}").format(leading.group(1), ", ".join(skills) or "none"),
			title=_("Unknown Skill"),
		)
	blocks = [_skill_block(skills[command]) for command in dict.fromkeys(commands) if command in skills]
	if not blocks:
		return text
	return "\n\n".join([*blocks, instructions] if instructions else blocks)


def _skill_block(row: dict) -> str:
	body = (frappe.db.get_value("Flow Skill", row["name"], "instructions") or "").strip()
	return (
		f'<skill name="{row["command"]}" location="Flow Skill/{escape(row["name"], quote=True)}">\n'
		f"{SKILL_LOADED_NOTE}\n\n{body}\n</skill>"
	)


def skill_command(title: str) -> str:
	"""What a user types after `/skill:` to start the skill: the title lowercased, each run of
	other characters as one hyphen."""
	return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
