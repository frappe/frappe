# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import re
from html import escape
from pathlib import Path

import frappe
from frappe import _
from frappe.flow.utils.system_generated import (
	block_delete,
	block_insert,
	block_rename,
	block_slash_in_name,
	log_skipped,
	skip_if_invalid,
	validate_immutable,
)
from frappe.model.document import Document

MAX_DESCRIPTION_LENGTH = 1024

# A global skill lands in every agent's prompt, so it is capped tighter than a bound one.
MAX_GLOBAL_SKILLS = 10

# The largest file load_skill reads from a skill's folder.
MAX_SKILL_FILE_BYTES = 256 * 1024

_SKILL_COMMAND_RE = re.compile(r"/skill:(\S+)(?:\s+(.*))?$", re.DOTALL)
# a "/skill:<command>" word anywhere in a message
_SKILL_TOKEN_RE = re.compile(r"(?<!\S)/skill:(\S+)")
# the frontmatter that opens a SKILL.md, matched as the harness matches it
_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n.*?\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)

# Rides inside the wrapper, unseen by the user: the agent's index still says to load skills.
SKILL_LOADED_NOTE = "This is the full skill, already loaded. Follow it; call load_skill only to read a file or folder it mentions."


class FlowSkill(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		app: DF.Data | None
		description: DF.SmallText
		enabled: DF.Check
		instructions: DF.LongText
		is_global: DF.Check
		is_system_generated: DF.Check
		title: DF.Data
		user_invocable: DF.Check
	# end: auto-generated types

	def before_insert(self):
		block_insert(self)

	def validate(self):
		block_slash_in_name(self)
		self._validate_description()
		self._validate_global_limit()
		self._validate_command()
		validate_immutable(self, ("description", "instructions"))

	def on_trash(self):
		block_delete(self)

	def before_rename(self, old: str, new: str, merge: bool = False) -> None:
		block_rename(self, old)
		block_slash_in_name(self, new)
		if not merge:
			self._validate_command(new)

	def _validate_description(self):
		"""Every bound skill's description rides in the agent's prompt, so keep it short."""
		if len(self.description or "") > MAX_DESCRIPTION_LENGTH:
			frappe.throw(
				_("Description must be at most {0} characters.").format(MAX_DESCRIPTION_LENGTH),
				title=_("Description Too Long"),
			)

	def _validate_command(self, name: str | None = None):
		"""A user-invocable skill answers to /skill:<command>, so its command must be typable and its own."""
		if not self.user_invocable:
			return
		command = skill_command(name or self.name or "")
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


def skill_command(name: str) -> str:
	"""What a user types after `/skill:` to start the skill: its name lowercased, each run of
	other characters as one hyphen."""
	return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def sync_skills() -> list[str]:
	"""Write each installed app's skills/<name>/SKILL.md as a locked Flow Skill named `<app>/<name>`
	and delete the app skills gone from disk. Returns the names written. A skill that cannot be
	written is skipped and logged, and its row kept as it was."""
	from flow_harness.session.skills import MAX_SKILL_DIRECTORY_ENTRIES, list_skill_files, load_skill

	shipped: dict[str, tuple[str, str, str]] = {}
	skills_to_keep: set[str] = set()
	for app in frappe.get_installed_apps(_ensure_on_bench=True):
		folder = frappe.get_app_source_path(app, "skills")
		paths, truncated = list_skill_files(folder)
		# a cut-off scan would delete the skills it missed
		if truncated:
			log_skipped(
				f"Flow Skills of {app} skipped",
				_("Skills folder {0} has more than {1} entries.").format(folder, MAX_SKILL_DIRECTORY_ENTRIES),
			)
			skills_to_keep.update(
				frappe.get_all("Flow Skill", {"is_system_generated": 1, "app": app}, pluck="name")
			)
			continue
		for path in paths:
			name = f"{app}/{Path(path).parent.name}"
			skills_to_keep.add(name)
			try:
				skill = load_skill(path)
				with open(path, encoding="utf-8") as file:  # nosemgrep: frappe-security-file-traversal
					instructions = _FRONTMATTER_RE.sub("", file.read(), count=1).strip()
			except ValueError as e:  # a SkillError, or a body that is not UTF-8
				log_skipped(f"Flow Skill {name} skipped", _("Invalid skill {0}: {1}").format(path, str(e)))
				continue
			shipped[name] = (app, skill.description, instructions)
	synced = []
	for name, (app, description, instructions) in shipped.items():
		with skip_if_invalid(f"Flow Skill {name} skipped"):
			_ensure_skill(name, app, description, instructions)
			synced.append(name)
	for name in frappe.get_all("Flow Skill", {"is_system_generated": 1}, pluck="name"):
		if name not in skills_to_keep:
			# unlink first: delete_doc refuses a skill an agent still uses
			frappe.db.delete("Flow Agent Skill", {"skill": name})
			frappe.delete_doc("Flow Skill", name, ignore_permissions=True)
	return sorted(synced)


def _ensure_skill(name: str, app: str, description: str, instructions: str) -> None:
	"""Create or update the locked Flow Skill for one app skill."""
	definition = {
		"app": app,
		"description": description,
		"instructions": instructions,
		"is_system_generated": 1,
	}
	row = frappe.db.get_value("Flow Skill", name, list(definition), as_dict=True)
	if row and all(row[key] == value for key, value in definition.items()):
		return
	if row:
		doc = frappe.get_doc("Flow Skill", name)
	else:
		doc = frappe.get_doc({"doctype": "Flow Skill", "title": name})
	doc.update(definition)
	doc.save(ignore_permissions=True)


def skill_file(name: str, file: str) -> str:
	"""A text file from the folder of an app's skill, by its path inside that folder. A folder
	gives the files in it."""
	from flow_harness.session.skills import valid_skill_name

	app = frappe.db.get_value("Flow Skill", name, "app")
	folder_name = name.removeprefix(f"{app}/")
	# rows can be written by hand, so trust only an installed app and a plain folder name
	if app not in frappe.get_installed_apps() or not valid_skill_name(folder_name):
		frappe.throw(_("Skill {0} has no files.").format(name), title=_("Unknown File"))
	folder = Path(frappe.get_app_source_path(app, "skills"), folder_name).resolve()
	path = (folder / file).resolve()
	hidden = any(part.startswith(".") for part in Path(file).parts)
	if hidden or not path.is_relative_to(folder) or not (path.is_file() or path.is_dir()):
		frappe.throw(_("Skill {0} has no file {1}.").format(name, file), title=_("Unknown File"))
	if path.is_dir():
		return _list_files(folder, path)
	if path.stat().st_size > MAX_SKILL_FILE_BYTES:
		frappe.throw(
			_("{0} is larger than {1} KB.").format(file, MAX_SKILL_FILE_BYTES // 1024),
			title=_("File Too Large"),
		)
	try:
		return path.read_text(encoding="utf-8")
	except UnicodeDecodeError:
		frappe.throw(_("{0} is not a text file.").format(file), title=_("Not a Text File"))


def _list_files(folder: Path, path: Path) -> str:
	"""The files under `path`, one per line, as paths inside the skill folder."""
	files = []
	for entry in path.rglob("*"):
		relative = entry.relative_to(folder)
		hidden = any(part.startswith(".") for part in relative.parts)
		if not hidden and entry.is_file() and entry.resolve().is_relative_to(folder):
			files.append(relative.as_posix())
	return "\n".join(sorted(files))
