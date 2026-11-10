# SETTINGS RULES — what a `Settings Dialog` record may hold, written once.

# `Settings Dialog` runs these on save and on import, migrate runs them over every shipped record,
# and the merge in `settings.py` runs them to decide which blocks to leave out.

import os
import re
from dataclasses import dataclass

import frappe
from frappe import _
from frappe.desk.settings_block import Block, Refusal, check_binding

# The address segment a pane or block is opened by: `#settings/<prefix>/<pane>/<block>`.
KEBAB_CASE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


@dataclass(frozen=True)
class Problem:
	"""One rule a pane or block breaks, named by app, record, pane, block key and row."""

	title: str
	detail: str
	app: str
	record: str
	pane: str | None = None
	key: str | None = None
	idx: int | None = None
	# True when only the other records could tell: the pane, or a block it clashes with.
	across: bool = False

	@property
	def message(self) -> str:
		where = [f"app {self.app}", f"record {self.record}"]
		if self.pane:
			where.append(f"pane {self.pane}")
		if self.key:
			where.append(f"block {self.key}")
		if self.idx:
			where.append(f"row {self.idx}")
		return f"{', '.join(where)}: {self.detail}"


@dataclass
class Vetting:
	accepted: list[Block]
	problems: list[Problem]


class SettingsRules:
	"""Reads the site once per instance: its roles, its doctypes and its apps' component files."""

	def __init__(self):
		self._roles: set[str] | None = None
		self._doctypes: dict[str, bool] = {}
		self._components: dict[str, set[str]] = {}

	def record_problems(self, record) -> list[Problem]:
		"""What the pane rows of one record break; its blocks are in `vet`."""
		problems = []
		seen = set()

		if record.extends and record.panes:
			problems.append(
				self._problem(
					record,
					_("Pane on a Host"),
					_("{0} extends {1}, so it can add blocks to its panes but no pane of its own.").format(
						frappe.bold(record.app), frappe.bold(record.extends)
					),
				)
			)

		for pane in record.panes:
			try:
				check_key(pane.key, _("Pane"))
				if pane.key in seen:
					raise Refusal(
						_("Duplicate Key"), _("Repeats the pane key {0}.").format(frappe.bold(pane.key))
					)
			except Refusal as refusal:
				problems.append(
					self._problem(record, refusal.title, refusal.detail, pane=pane.key, idx=pane.idx)
				)
			seen.add(pane.key)

		return problems

	def vet(self, panes: set[str] | None, contributors: list) -> Vetting:
		"""The blocks of these records, in order, that may sit in the host's `panes`, and why the rest may not.

		A block bound to a doctype this site lacks is left out with no problem. `panes` is None when the host is not known.
		"""
		kept: dict[str, list[Block]] = {}
		accepted, problems = [], []

		for record in contributors:
			for row in record.blocks:
				block = Block(record, row)
				try:
					self._check_alone(block)
					if panes is not None and block.pane not in panes:
						raise Refusal(
							_("Unknown Pane"),
							_("The pane {0} is not one {1} ships.").format(
								frappe.bold(block.pane), frappe.bold(record.extends or record.app)
							),
							across=bool(record.extends),
						)
					if not all(self._has_doctype(doctype) for doctype in block.doctypes):
						continue
					check_clash(block, kept.setdefault(block.pane, []))
				except Refusal as refusal:
					problems.append(self._problem_for(block, refusal))
					continue

				kept[block.pane].append(block)
				accepted.append(block)

		return Vetting(accepted, problems)

	def _check_alone(self, block: Block):
		"""Every rule that needs this block and the site only."""
		row = block.row
		check_key(block.key, _("Block"))

		if row.binding_type and row.component:
			raise Refusal(_("Invalid Block"), _("Either a generated binding or a component, not both."))
		if not row.binding_type and not row.component:
			raise Refusal(_("Invalid Block"), _("Needs a binding type or a component."))

		if row.binding_type:
			check_binding(row.binding_type, row.document_type, row.name_resolver)
			block.fields
		else:
			block.bindings, block.fields, block.settings
			self._check_fields(block)
			self._check_component_file(block)

		block.anchors
		self._check_roles(block)

	def _check_fields(self, block: Block):
		"""A bound component saves only the fields it lists. Their names go unchecked while a bound doctype is not installed."""
		if block.bindings and not block.fields:
			raise Refusal(
				_("Fields Not Listed"),
				_("Component {0} has a binding. List the fields it saves in {1}.").format(
					frappe.bold(block.row.component),
					frappe.bold(frappe.get_meta("Settings Block").get_label("fields")),
				),
			)

		if not block.bindings or not all(self._has_doctype(doctype) for doctype in block.doctypes):
			return

		metas = [frappe.get_meta(doctype) for doctype in block.doctypes]
		if missing := [field for field in block.fields if not any(meta.has_field(field) for meta in metas)]:
			raise Refusal(
				_("Unknown Field"),
				_("Not a field of {0}: {1}.").format(
					frappe.bold(", ".join(block.doctypes)), frappe.bold(", ".join(missing))
				),
			)

	def _check_roles(self, block: Block):
		if self._roles is None:
			self._roles = set(frappe.get_all("Role", pluck="name"))

		if unknown := sorted(set(block.roles) - self._roles):
			raise Refusal(_("Unknown Role"), _("No role named {0}.").format(frappe.bold(", ".join(unknown))))

	def _check_component_file(self, block: Block):
		"""The file `frontend/plugin/contributions.js` finds: `<module>/frontend/settings/<name>.vue` in the block's app."""
		if block.app not in frappe.get_installed_apps():
			return

		if block.row.component not in self._component_files(block.app):
			raise Refusal(
				_("Component Missing"),
				_("The component {0} has no file {1} in any module of {2}.").format(
					frappe.bold(block.row.component),
					frappe.bold(f"<module>/frontend/settings/{block.row.component}.vue"),
					frappe.bold(block.app),
				),
			)

	def _component_files(self, app: str) -> set[str]:
		if app not in self._components:
			root = frappe.get_app_path(app)
			names = set()
			for module in os.scandir(root):
				folder = os.path.join(module.path, "frontend", "settings")
				if module.is_dir() and os.path.isdir(folder):
					names |= {name[: -len(".vue")] for name in os.listdir(folder) if name.endswith(".vue")}
			self._components[app] = names
		return self._components[app]

	def _has_doctype(self, doctype: str) -> bool:
		if doctype not in self._doctypes:
			self._doctypes[doctype] = bool(frappe.db.exists("DocType", doctype))
		return self._doctypes[doctype]

	def _problem_for(self, block: Block, refusal: Refusal) -> Problem:
		return self._problem(
			block.record,
			refusal.title,
			refusal.detail,
			pane=block.pane,
			key=block.key,
			idx=block.row.idx,
			across=refusal.across,
		)

	def _problem(self, record, title, detail, **where) -> Problem:
		return Problem(title, detail, record.app, record.name, **where)


def check_clash(block: Block, kept: list[Block]):
	"""Raise when `block` cannot sit beside the blocks already kept in its pane."""
	for other in kept:
		if other.key == block.key:
			raise Refusal(
				_("Duplicate Key"),
				_("{0} already ships a block {1} in this pane.").format(
					frappe.bold(other.app), frappe.bold(block.key)
				),
				across=other.record.name != block.record.name,
			)

		shared = block.addresses & other.addresses
		if not shared:
			continue

		# Component blocks on one draft can own the same fields, so an `auto` commit would send a `button` block's edits.
		if other.save_mode != block.save_mode:
			raise Refusal(
				_("Mixed Save Modes"),
				_("Component blocks {0} from {1} and {2} both edit {3}, so they need one save mode.").format(
					*[frappe.bold(part) for part in (other.key, other.app, block.key, sorted(shared)[0][0])]
				),
				across=True,
			)

		# A component block saves and shows refusals for the fields it owns, so one field has one owner per draft.
		if fields := block.owned_fields & other.owned_fields:
			raise Refusal(
				_("Field Declared Twice"),
				_(
					"Component blocks {0} from {1} and {2} from {3} both declare {4}. List each field in one block only."
				).format(
					*[
						frappe.bold(part)
						for part in (other.key, other.app, block.key, block.app, ", ".join(sorted(fields)))
					]
				),
				across=True,
			)


def check_key(key: str, kind: str):
	if not KEBAB_CASE.match(key or ""):
		raise Refusal(
			_("Invalid Key"),
			_("The {0} key {1} must be kebab-case, like {2}.").format(
				kind, frappe.bold(key), frappe.bold("email-accounts")
			),
		)


def is_strict() -> bool:
	return bool(frappe.conf.developer_mode or frappe.in_test or os.environ.get("CI"))


def report(problems: list[Problem]):
	"""Raise in developer mode, in tests and in CI; on a production site print and log them, and go on."""
	if not problems:
		return

	if is_strict():
		frappe.throw("<br>".join(problem.message for problem in problems), title=_("Settings Dialog"))

	message = "\n".join(problem.message for problem in problems)
	print(message)
	frappe.log_error(title="Settings Dialog records break a rule", message=message)
