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
	"""`/skill:<command> [instructions]` becomes the skill's instructions in the flow server's
	own wrapper, which the chat shows as the command again. Any other text passes through."""
	match = _SKILL_COMMAND_RE.match(text.strip())
	if not match:
		return text
	command, instructions = match.group(1), (match.group(2) or "").strip()
	skills = frappe.get_doc("Flow Agent", agent).invocable_skills()
	row = next((row for row in skills if row["command"] == command), None)
	if row is None:
		frappe.throw(
			_("No skill named {0}. Available: {1}").format(
				command, ", ".join(row["command"] for row in skills) or "none"
			),
			title=_("Unknown Skill"),
		)
	body = (frappe.db.get_value("Flow Skill", row["name"], "instructions") or "").strip()
	block = (
		f'<skill name="{command}" location="Flow Skill/{escape(row["name"], quote=True)}">\n'
		f"{SKILL_LOADED_NOTE}\n\n{body}\n</skill>"
	)
	return f"{block}\n\n{instructions}" if instructions else block


def skill_command(title: str) -> str:
	"""What a user types after `/skill:` to start the skill: the title lowercased, each run of
	other characters as one hyphen."""
	return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
