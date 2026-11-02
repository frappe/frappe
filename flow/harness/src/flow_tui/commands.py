"""Command registry — one table behind both the composer's slash dispatch and the
command palette.

Each command is an async function over `(app, arg)`. The composer feeds lines that
start with `/`; the palette (`FlowCommandProvider`) fuzzy-matches the same registry,
so the two surfaces can never drift apart. `CommandError` carries a user-facing
message; `dispatch` turns it (and API errors) into a toast.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, cast, get_args

from textual.command import DiscoveryHit, Hit, Hits, Provider

from flow_harness.events import ReasoningEffort, UserMessage
from flow_harness.session.skills import parse_skill_invocation
from flow_tui.client.api import FlowAPIError
from flow_tui.screens.pickers import EffortPicker, ModelPicker, SessionPicker

if TYPE_CHECKING:
	from flow_tui.app import FlowApp


class CommandError(Exception):
	"""The command line could not be parsed or executed; the message is user-facing."""


@dataclass(frozen=True)
class Command:
	name: str
	description: str
	run: Callable[["FlowApp", str], Awaitable[None]]
	arg_hint: str = ""

	@property
	def usage(self) -> str:
		return f"/{self.name} {self.arg_hint}".strip()


REGISTRY: dict[str, Command] = {}


def command(name: str, description: str, arg_hint: str = ""):
	def register(run: Callable[["FlowApp", str], Awaitable[None]]):
		REGISTRY[name] = Command(name=name, description=description, run=run, arg_hint=arg_hint)
		return run

	return register


def parse(line: str) -> tuple[Command, str]:
	"""Split a `/name arg…` line into its command and argument string."""
	name, _, arg = line[1:].partition(" ")
	found = REGISTRY.get(name)
	if found is None:
		raise CommandError(f"unknown command: /{name} — /help lists commands")
	return found, arg.strip()


async def dispatch(app: "FlowApp", line: str) -> None:
	try:
		found, arg = parse(line)
		await found.run(app, arg)
	except CommandError as error:
		app.notify(str(error), severity="error")
	except FlowAPIError as error:
		app.notify(str(error.detail), severity="error", markup=False)


# --- commands ---------------------------------------------------------------

EFFORT_LEVELS: tuple[str, ...] = get_args(ReasoningEffort)


@command("model", "switch the model for runs from here on; no arg opens the picker", arg_hint="[name]")
async def _model(app: "FlowApp", arg: str) -> None:
	if not arg:
		catalog = await app.controller.list_models()
		for error in catalog.get("errors", []):
			app.notify(f"model discovery: {error}", severity="warning", markup=False)
		arg = await app.push_screen_wait(ModelPicker(catalog["models"])) or ""
		if not arg:
			return
	await app.controller.change_model(arg)


@command(
	"effort",
	"set reasoning effort; no arg opens the picker",
	arg_hint="[default|" + "|".join(EFFORT_LEVELS) + "]",
)
async def _effort(app: "FlowApp", arg: str) -> None:
	if not arg:
		arg = await app.push_screen_wait(EffortPicker(app.controller.state.reasoning_effort)) or ""
		if not arg:
			return
	if arg == "default":
		await app.controller.change_effort(None)
	elif arg in EFFORT_LEVELS:
		await app.controller.change_effort(cast(ReasoningEffort, arg))
	else:
		raise CommandError(f"usage: {REGISTRY['effort'].usage}")


@command("abort", "abort the active run")
async def _abort(app: "FlowApp", arg: str) -> None:
	await app.controller.abort()


@command("rewind", "rewind the conversation; no seq drops the last user message", arg_hint="[seq]")
async def _rewind(app: "FlowApp", arg: str) -> None:
	if arg:
		try:
			target = int(arg)
		except ValueError:
			raise CommandError(f"usage: {REGISTRY['rewind'].usage}") from None
		await app.controller.rewind(target)
		return
	# default: cut back to just before the last user message, and put its text back in
	# the composer so the user can rephrase and resend
	entries = app.controller.state.entries
	last_user = next((entry for entry in reversed(entries) if isinstance(entry, UserMessage)), None)
	if last_user is None:
		raise CommandError("nothing to rewind")
	target = max(
		(entry.seq for entry in entries if entry.seq is not None and entry.seq < (last_user.seq or 0)),
		default=0,
	)
	await app.controller.rewind(target)
	invocation = parse_skill_invocation(last_user.text)
	app.prefill_composer(invocation.command if invocation is not None else last_user.text)


@command("clear", "start a fresh session (alias for /new)")
@command("new", "start a fresh session")
async def _new(app: "FlowApp", arg: str) -> None:
	sid = await app.controller.new_session()
	app.notify(f"new session {sid[:8]}", markup=False)


@command("resume", "switch to another session; no arg opens the picker", arg_hint="[id]")
async def _resume(app: "FlowApp", arg: str) -> None:
	sessions = await app.controller.list_sessions()
	if not sessions:
		raise CommandError("no sessions on this daemon")
	if not arg:
		sid = await app.push_screen_wait(SessionPicker(sessions, app.controller.session_id)) or ""
		if not sid:
			return
	else:
		matches = [s for s in sessions if s["session_id"].startswith(arg)]
		if not matches:
			raise CommandError(f"no session matches {arg!r}")
		if len(matches) > 1:
			raise CommandError(f"{arg!r} is ambiguous ({len(matches)} sessions match)")
		sid = matches[0]["session_id"]
	if sid == app.controller.session_id:
		raise CommandError("already on that session")
	await app.controller.switch_session(sid)
	app.notify(f"switched to {sid[:8]}", markup=False)


@command("reload", "reload server extensions; new tools apply from the next run")
async def _reload(app: "FlowApp", arg: str) -> None:
	info = await app.controller.reload_extensions()
	names = [extension["name"] for extension in info["extensions"]]
	app.notify(f"extensions reloaded: {', '.join(names) if names else 'none loaded'}", markup=False)
	for diagnostic in info["diagnostics"]:
		if diagnostic.get("severity") == "error":
			app.notify(f"extension error: {diagnostic['message']}", severity="warning", markup=False)


@command("editor", "edit the draft in $VISUAL/$EDITOR (ctrl+x ctrl+e); the editor must block, e.g. `code -w`")
async def _editor(app: "FlowApp", arg: str) -> None:
	app.action_edit_in_editor()


@command("help", "list commands")
async def _help(app: "FlowApp", arg: str) -> None:
	lines = [f"{found.usage} — {found.description}" for found in REGISTRY.values()]
	app.notify("\n".join(lines), title="commands", timeout=10, markup=False)


@command("quit", "quit flow")
async def _quit(app: "FlowApp", arg: str) -> None:
	app.exit()


# --- palette ----------------------------------------------------------------


class FlowCommandProvider(Provider):
	"""Feeds textual's command palette from the same registry as slash commands."""

	async def search(self, query: str) -> Hits:
		matcher = self.matcher(query)
		app = cast("FlowApp", self.app)
		for skill in getattr(app.controller, "skills", []):
			name = f"/skill:{skill['name']}"
			score = matcher.match(name)
			if score > 0:
				yield Hit(
					score,
					matcher.highlight(name),
					partial(self._insert_skill, skill["name"]),
					help=skill["description"],
				)
		for found in REGISTRY.values():
			score = matcher.match(f"/{found.name}")
			if score > 0:
				yield Hit(
					score,
					matcher.highlight(f"/{found.name}"),
					partial(self._execute, found),
					help=found.description,
				)

	async def discover(self) -> Hits:
		app = cast("FlowApp", self.app)
		for skill in getattr(app.controller, "skills", []):
			yield DiscoveryHit(
				f"/skill:{skill['name']}",
				partial(self._insert_skill, skill["name"]),
				help=skill["description"],
			)
		for found in REGISTRY.values():
			yield DiscoveryHit(f"/{found.name}", partial(self._execute, found), help=found.description)

	def _insert_skill(self, name: str) -> None:
		cast("FlowApp", self.app).prefill_composer(f"/skill:{name} ")

	def _execute(self, found: Command) -> None:
		app = cast("FlowApp", self.app)
		app.run_worker(dispatch(app, f"/{found.name}"), exclusive=False)
