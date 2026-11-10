# SETTINGS ARRANGEMENT — what an app's `arrangement` may hold, and the references it keeps.

# Panes and blocks are named by prefix address: `desk/profile`, `desk/profile/telephony`.
# `ArrangementCheck` drops the parts that break a rule, so the resolver never meets one.

import json

import frappe
from frappe import _
from frappe.desk.app_prefix import declared_prefix, default_prefix
from frappe.desk.settings_block import Refusal
from frappe.desk.settings_rules import Problem

KEYS = ("groups", "hidden", "panes")
PANE_KEYS = ("blocks", "hidden")
PARTS = {"pane": 2, "block": 3}
EXAMPLES = {"pane": "desk/profile", "block": "desk/profile/telephony"}


def prefix_of(app: str, bench: list[str] | None = None) -> str:
	"""The prefix an app is addressed by; an app the bench lacks gets the one it would derive."""
	on_bench = bench if bench is not None else frappe.get_all_apps()
	return declared_prefix(app) if app in on_bench else default_prefix(app)


class Directory:
	"""The panes and blocks of the apps in scope by address, and which prefix belongs to which app."""

	def __init__(self, panes: list[dict], apps: list[str]):
		bench = frappe.get_all_apps()
		self.apps = set(apps)
		self.prefixes = {app: prefix_of(app, bench) for app in dict.fromkeys([*bench, *apps])}
		self.owners = {prefix: app for app, prefix in self.prefixes.items()}
		self.panes: dict[str, dict] = {}
		self.blocks: dict[str, dict] = {}

		for pane in panes:
			address = self.pane_address(pane)
			self.panes[address] = pane
			self.blocks.update({f"{address}/{block['key']}": block for block in pane["blocks"]})

	def pane_address(self, pane: dict) -> str:
		return f"{self.prefixes[pane['app']]}/{pane['key']}"

	def lookup(self, address: str, kind: str) -> bool:
		"""Whether `address` names a `kind` here (False for an app out of scope); a `Refusal` if it names nothing."""
		prefix = address.split("/")[0]

		if prefix not in self.owners:
			raise Refusal(_("Unknown Prefix"), self._prefix_detail(address, prefix), across=True)

		if self.owners[prefix] not in self.apps:
			return False

		if address not in (self.panes if kind == "pane" else self.blocks):
			raise Refusal(
				_("Unknown Address"), _("No {0} has the address {1}.").format(kind, address), across=True
			)

		return True

	def _prefix_detail(self, address: str, prefix: str) -> str:
		if prefix in self.prefixes:
			hint = "/".join([self.prefixes[prefix], *address.split("/")[1:]])
			return _("No app has the prefix {0}. Did you mean {1}?").format(prefix, hint)

		return _("No app has the prefix {0}.").format(prefix)


class ArrangementCheck:
	"""One record's `arrangement` read and the problems of what it dropped; a `Directory` adds the address checks."""

	def __init__(self, record, directory: Directory | None = None):
		self.record = record
		self.directory = directory
		self.problems: list[Problem] = []

	def check(self) -> list[Problem]:
		"""The problems of this record alone."""
		self.run()
		return self.problems

	def run(self) -> dict | None:
		"""The arrangement with every part that breaks a rule dropped; None when the record has none."""
		raw = self._load()
		if raw is None:
			return None

		if self.record.extends:
			self._drop(
				"arrangement",
				_("Arrangement on an Extender"),
				_("{0} extends {1}. Only the app that owns a desk arranges its sidebar.").format(
					self.record.app, self.record.extends
				),
			)
			return None

		arrangement = self._shape(raw)
		self._conflicts(arrangement)

		if self.directory:
			self._references(arrangement)

		return arrangement

	def _load(self):
		raw = self.record.arrangement
		if isinstance(raw, str):
			if not raw.strip():
				return None
			try:
				raw = json.loads(raw)
			except ValueError:
				self._drop("arrangement", _("Invalid JSON"), _("Does not hold the JSON it should."))
				return None

		return None if raw is None or raw == {} else raw

	# The shape

	def _shape(self, raw) -> dict:
		if not isinstance(raw, dict):
			self._drop("arrangement", _("Invalid Arrangement"), _("Must be an object."))
			raw = {}

		self._unknown_keys(raw, KEYS, "arrangement")
		return {
			"groups": self._groups(raw.get("groups", [])),
			"hidden": self._addresses(raw.get("hidden", []), "arrangement.hidden", "pane"),
			"panes": self._pane_entries(raw.get("panes", {})),
		}

	def _groups(self, raw) -> list[dict]:
		if not isinstance(raw, list):
			self._drop("arrangement.groups", _("Invalid Arrangement"), _("Must be a list."))
			return []

		groups = []
		for index, entry in enumerate(raw):
			path = f"arrangement.groups[{index}]"
			if not isinstance(entry, dict):
				self._drop(path, _("Invalid Arrangement"), _("Must be an object."))
				continue

			self._unknown_keys(entry, ("label", "panes"), path)
			label = entry.get("label")
			if label is not None and not (isinstance(label, str) and label.strip()):
				self._drop(f"{path}.label", _("Invalid Label"), _("Must be text."))
				label = None

			# Only the first group is drawn without a heading, as the framework's list is.
			if index and not label:
				self._drop(path, _("Group Without Label"), _("Only the first group may have no label."))
				continue

			panes = self._addresses(entry.get("panes", []), f"{path}.panes", "pane")
			groups.append({"label": label, "panes": panes} if label else {"panes": panes})

		return groups

	def _pane_entries(self, raw) -> dict[str, dict]:
		if not isinstance(raw, dict):
			self._drop("arrangement.panes", _("Invalid Arrangement"), _("Must be an object."))
			return {}

		entries = {}
		for address, entry in raw.items():
			path = f'arrangement.panes["{address}"]'
			if not self._is_address(address, "pane", path):
				continue
			if not isinstance(entry, dict):
				self._drop(path, _("Invalid Arrangement"), _("Must be an object."))
				continue

			self._unknown_keys(entry, PANE_KEYS, path)
			entries[address] = {
				key: self._addresses(entry.get(key, []), f"{path}.{key}", "block") for key in PANE_KEYS
			}

		return entries

	def _addresses(self, raw, path: str, kind: str) -> list[str]:
		if not isinstance(raw, list):
			self._drop(path, _("Invalid Arrangement"), _("Must be a list."))
			return []

		return [
			address
			for index, address in enumerate(raw)
			if self._is_address(address, kind, f"{path}[{index}]")
		]

	def _is_address(self, address, kind: str, path: str) -> bool:
		parts = address.split("/") if isinstance(address, str) else []
		if len(parts) == PARTS[kind] and all(parts):
			return True

		self._drop(
			path,
			_("Invalid Address"),
			_("{0} is not a {1} address, like {2}.").format(address, kind, EXAMPLES[kind]),
		)
		return False

	def _unknown_keys(self, entry: dict, known: tuple, path: str):
		for key in entry.keys() - set(known):
			self._drop(
				f"{path}.{key}", _("Unknown Key"), _("The keys here are: {0}.").format(", ".join(known))
			)

	# Rules that need this record only

	def _conflicts(self, arrangement: dict):
		own_prefix = prefix_of(self.record.app)
		grouped = self._grouped(arrangement["groups"])
		hidden = self._unique(arrangement["hidden"])

		kept = []
		for index, address in enumerate(hidden):
			path = f"arrangement.hidden[{index}]"
			if address in grouped:
				self._drop(path, _("Pane Placed and Hidden"), _("{0} is also in a group.").format(address))
			elif address.split("/")[0] == own_prefix:
				self._drop(
					path, _("Hiding Own Pane"), _("An app does not hide its own pane {0}.").format(address)
				)
			else:
				kept.append(address)

		arrangement["hidden"] = kept
		arrangement["panes"] = {
			address: self._pane_entry(address, entry, grouped, set(kept))
			for address, entry in arrangement["panes"].items()
			if self._has_place(address, grouped, set(kept))
		}

	def _grouped(self, groups: list[dict]) -> dict[str, str]:
		"""`{address: path}` of the first group holding each pane; a pane in a second group is dropped from it."""
		grouped: dict[str, str] = {}
		for g, group in enumerate(groups):
			kept = []
			for p, address in enumerate(group["panes"]):
				path = f"arrangement.groups[{g}].panes[{p}]"
				if address in grouped:
					self._drop(
						path,
						_("Pane in Two Groups"),
						_("{0} is also at {1}.").format(address, grouped[address]),
					)
					continue
				grouped[address] = path
				kept.append(address)
			group["panes"] = kept

		return grouped

	def _has_place(self, address: str, grouped: dict, hidden: set) -> bool:
		path = f'arrangement.panes["{address}"]'
		if address in hidden:
			self._drop(
				path,
				_("Hidden Pane Arranged"),
				_("{0} is hidden, so its blocks are not arranged.").format(address),
			)
		elif address not in grouped:
			self._drop(path, _("Ungrouped Pane Arranged"), _("{0} is in no group.").format(address))
		else:
			return True

		return False

	def _pane_entry(self, address: str, entry: dict, grouped: dict, hidden: set) -> dict:
		path = f'arrangement.panes["{address}"]'
		listed = {}
		blocks = []
		for index, block in enumerate(entry["blocks"]):
			if block in listed:
				self._drop(
					f"{path}.blocks[{index}]",
					_("Block Listed Twice"),
					_("{0} is also at {1}.").format(block, listed[block]),
				)
				continue
			listed[block] = f"{path}.blocks[{index}]"
			blocks.append(block)

		hidden_blocks = []
		for index, block in enumerate(self._unique(entry["hidden"])):
			if block in listed:
				self._drop(
					f"{path}.hidden[{index}]",
					_("Block Listed and Hidden"),
					_("{0} is also at {1}.").format(block, listed[block]),
				)
			else:
				hidden_blocks.append(block)

		return {"blocks": blocks, "hidden": hidden_blocks}

	@staticmethod
	def _unique(values: list[str]) -> list[str]:
		return list(dict.fromkeys(values))

	# Rules that need the site

	def _references(self, arrangement: dict):
		"""Drop every address that names nothing, or an app that is not active here, and say which."""
		for group_index, group in enumerate(arrangement["groups"]):
			path = f"arrangement.groups[{group_index}].panes"
			group["panes"] = self._existing(group["panes"], path, "pane")

		arrangement["hidden"] = self._existing(arrangement["hidden"], "arrangement.hidden", "pane")

		for address in list(arrangement["panes"]):
			path = f'arrangement.panes["{address}"]'
			if not self._existing([address], path, "pane", indexed=False):
				del arrangement["panes"][address]
				continue
			entry = arrangement["panes"][address]
			for key in PANE_KEYS:
				entry[key] = self._existing(entry[key], f"{path}.{key}", "block")

	def _existing(self, addresses: list[str], path: str, kind: str, indexed: bool = True) -> list[str]:
		kept = []
		for index, address in enumerate(addresses):
			try:
				if self.directory.lookup(address, kind):
					kept.append(address)
			except Refusal as refusal:
				self._drop(
					f"{path}[{index}]" if indexed else path, refusal.title, refusal.detail, across=True
				)

		return kept

	def _drop(self, path: str, title: str, detail: str, across: bool = False):
		record = self.record
		self.problems.append(Problem(title, f"{path}: {detail}", record.app, record.name, across=across))
