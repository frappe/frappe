# SETTINGS SIDEBAR — the sidebar each desk shows, resolved from the apps' arrangements.

# One sidebar per prefix: groups of panes, and under each pane the addresses of the blocks it
# shows. The sidebar of a desk comes from the arrangement of the app that owns it; an app with
# none gets the framework's panes, then its own. Unfiltered, so one merge serves every user.

from dataclasses import dataclass, field

from frappe.desk.settings_arrangement import ArrangementCheck, Directory, prefix_of
from frappe.desk.settings_rules import Problem

FRAMEWORK = "frappe"


@dataclass
class Resolved:
	"""The merged panes, the sidebars by prefix, the problems of what an arrangement dropped, and the notices by prefix."""

	panes: list[dict] = field(default_factory=list)
	sidebars: dict[str, dict] = field(default_factory=dict)
	problems: list[Problem] = field(default_factory=list)
	notices: dict[str, list[str]] = field(default_factory=dict)
	directory: Directory | None = None


def resolve_sidebars(panes: list[dict], records: list, apps: list[str]) -> Resolved:
	"""The sidebar of every app that has panes or an arrangement, over the merged `panes` of `apps`."""
	directory = Directory(panes, apps)
	hosts = {record.app: record for record in records if not record.extends}
	resolved = Resolved(directory=directory)

	for app in apps:
		host = hosts.get(app)
		if app != FRAMEWORK and not (any(pane["app"] == app for pane in panes) or host):
			continue

		check = ArrangementCheck(host, directory) if host else None
		arrangement = check.run() if check else None
		builder = SidebarBuilder(directory, app, arrangement, host)
		prefix = directory.prefixes[app]
		resolved.sidebars[prefix] = builder.build()
		resolved.notices[prefix] = builder.notices
		resolved.problems += [*(check.problems if check else []), *builder.problems]

	return resolved


class SidebarBuilder:
	"""The sidebar of one desk app from its cleaned arrangement, or the default when it has none."""

	def __init__(self, directory: Directory, app: str, arrangement: dict | None, record):
		self.directory = directory
		self.app = app
		self.arrangement = arrangement
		self.record = record
		self.problems: list[Problem] = []
		self.notices: list[str] = []

	def build(self) -> dict:
		if self.arrangement is None:
			return {"groups": self._default_groups(), "hidden": [], "hidden_blocks": []}

		return {
			"groups": self._arranged_groups(),
			"hidden": list(self.arrangement["hidden"]),
			"hidden_blocks": [
				block for entry in self.arrangement["panes"].values() for block in entry["hidden"]
			],
		}

	def _default_groups(self) -> list[dict]:
		"""The framework's panes with no heading, then the app's own."""
		groups = [{"panes": self._entries(self._panes_of(FRAMEWORK), self._home_blocks)}]
		own = self._panes_of(self.app)

		if self.app != FRAMEWORK and own:
			groups.append({"app": self.app, "panes": self._entries(own, self._home_blocks)})

		return [group for group in groups if group["panes"]]

	def _arranged_groups(self) -> list[dict]:
		groups = [
			{**group, "panes": self._entries(group["panes"], self._arranged_blocks)}
			for group in self.arrangement["groups"]
		]
		mentioned = {address for group in self.arrangement["groups"] for address in group["panes"]}
		mentioned |= set(self.arrangement["hidden"])
		loose = [
			address
			for address in dict.fromkeys([*self._panes_of(FRAMEWORK), *self._panes_of(self.app)])
			if address not in mentioned
		]

		for address in loose:
			self.notices.append(
				f"{address} is in no group and not hidden. It goes in a last group, after the others."
			)

		return [*groups, *([{"panes": self._entries(loose, self._arranged_blocks)}] if loose else [])]

	def _arranged_blocks(self, address: str) -> list[str]:
		"""The pane's listed blocks, then its own that the entry neither lists nor hides."""
		home = self._home_blocks(address)
		entry = self.arrangement["panes"].get(address)
		if entry is None:
			return home

		remaining = [block for block in home if block not in entry["hidden"]]
		home_keys = {_key(block) for block in remaining}
		blocks, placed_keys = [], set()

		for index, block in enumerate(entry["blocks"]):
			if block not in home and (_key(block) in home_keys or _key(block) in placed_keys):
				self._duplicate(block, f'arrangement.panes["{address}"].blocks[{index}]', address)
				continue
			if block not in home:
				placed_keys.add(_key(block))
			blocks.append(block)

		for block in remaining:
			if block not in blocks:
				blocks.append(block)
				self.notices.append(
					f'{block} is not in arrangement.panes["{address}"].blocks or hidden. '
					f"It goes at the end of {address}."
				)

		return blocks

	def _duplicate(self, block: str, path: str, address: str):
		self.problems.append(
			Problem(
				"Duplicate Key",
				f"{path}: {address} already has a block with the key {_key(block)}.",
				self.record.app,
				self.record.name,
				across=True,
			)
		)

	def _entries(self, addresses: list[str], blocks_of) -> list[dict]:
		return [{"pane": address, "blocks": blocks_of(address)} for address in addresses]

	def _home_blocks(self, address: str) -> list[str]:
		return [f"{address}/{block['key']}" for block in self.directory.panes[address]["blocks"]]

	def _panes_of(self, app: str) -> list[str]:
		return [
			address for address, pane in self.directory.panes.items() if pane["app"] == app
		]


def filter_sidebar(sidebar: dict, panes: list[dict]) -> dict:
	"""The sidebar without the blocks that are not in `panes` (one user's visible panes), and without an emptied pane or group."""
	prefixes: dict[str, str] = {}
	visible = {
		f"{prefixes.setdefault(pane['app'], prefix_of(pane['app']))}/{pane['key']}/{block['key']}"
		for pane in panes
		for block in pane["blocks"]
	}
	groups = []

	for group in sidebar["groups"]:
		entries = [
			{**entry, "blocks": [block for block in entry["blocks"] if block in visible]}
			for entry in group["panes"]
		]
		if entries := [entry for entry in entries if entry["blocks"]]:
			groups.append({**group, "panes": entries})

	return {**sidebar, "groups": groups}


def _key(address: str) -> str:
	return address.rsplit("/", 1)[1]
