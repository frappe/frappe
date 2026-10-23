"""Extension discovery, loading, tool integration, and tool hooks."""

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from flow_harness import config as server_config
from flow_harness.events import AssistantMessage, ToolCall
from flow_harness.extensions import ExtensionRuntime
from flow_harness.model.mock import MockModel
from flow_harness.server import create_app
from flow_harness.server.policy import ServerPolicy
from flow_harness.session.config import SessionConfig
from flow_harness.session.store import SessionStore

HELLO_EXTENSION = """
from flow_harness.tools import ToolResult, tool

@tool(prompt_snippet="Greet someone by name.", display_template="Greeting {{ who }}")
async def hello(who: str = "world", *, ctx):
    return ToolResult(content=f"Hello, {who}!")

def setup(flow):
    flow.register_tool(hello)
"""

_DONE = AssistantMessage(content="done")


def _write_extension(directory: Path, name: str, body: str) -> Path:
	directory.mkdir(parents=True, exist_ok=True)
	path = directory / f"{name}.py"
	path.write_text(body)
	return path


def test_runtime_loads_extensions_in_order_and_isolates_failures(tmp_path):
	folder = tmp_path / "extensions"
	_write_extension(folder, "broken", "raise RuntimeError('boom')\n")
	_write_extension(folder, "hello", HELLO_EXTENSION)
	_write_extension(folder, "bad_event", "def setup(flow):\n    flow.on('turn_start', lambda event: None)\n")
	package = folder / "greeter"
	package.mkdir()
	(package / "helper.py").write_text("GREETING = 'Hi'\n")
	(package / "extension.py").write_text(
		"from .helper import GREETING\n"
		"from flow_harness.tools import ToolResult, tool\n"
		"\n"
		"@tool\n"
		"async def greet(*, ctx):\n"
		"    return ToolResult(content=GREETING)\n"
		"\n"
		"def setup(flow):\n"
		"    flow.register_tool(greet)\n"
	)
	explicit = _write_extension(
		tmp_path / "elsewhere",
		"gate",
		"def setup(flow):\n"
		"    flow.on('tool_call', lambda event: None)\n"
		"    flow.on('tool_result', lambda event: None)\n",
	)
	runtime = ExtensionRuntime()

	runtime.load(global_dir=folder, extra_paths=(explicit,))

	# the global folder in name order, then explicit paths; a broken one does not block the rest
	assert [item.name for item in runtime.extensions] == ["greeter", "hello", "gate"]
	assert list(runtime.tools) == ["greet", "hello"]  # greeter is a package with relative imports
	assert runtime.info()["extensions"][-1]["hooks"] == ["tool_call", "tool_result"]
	assert [(item.extension, item.severity) for item in runtime.diagnostics] == [
		("broken", "error"),
		("bad_event", "error"),
	]
	assert "failed to import extension" in runtime.diagnostics[0].message
	assert "unknown hook event" in runtime.diagnostics[1].message


def test_store_loads_extensions_once_and_reloads_them(tmp_path, monkeypatch):
	marker = tmp_path / "imports.txt"
	counting = f"from pathlib import Path\nwith Path({str(marker)!r}).open('a') as f:\n    f.write('x')\n"
	path = _write_extension(tmp_path / "global", "hello", counting + HELLO_EXTENSION)
	monkeypatch.setattr(server_config, "EXTENSIONS_PATH", str(tmp_path / "global"))
	assert SessionStore(str(tmp_path / "off")).extension_runtime.tools == {}  # the global folder is opt-in

	store = SessionStore(str(tmp_path / "data"), extensions_enabled=True)
	session = store.create(SessionConfig(cwd=str(tmp_path), tools=[]))
	store.create(SessionConfig(cwd=str(tmp_path), tools=[]))
	assert marker.read_text() == "x"  # imported once per store, not per session
	assert list(session.server_tools) == ["hello"]
	before = {name for name in sys.modules if name.startswith("flow_extension_")}

	path.write_text(counting + HELLO_EXTENSION.replace("hello", "howdy_tool"))
	store.reload_extensions()

	assert list(store.extension_runtime.tools) == ["howdy_tool"]
	assert list(session.server_tools) == ["howdy_tool"]  # cached sessions swap too
	assert store.extension_runtime.diagnostics == ()
	after = {name for name in sys.modules if name.startswith("flow_extension_")}
	assert not before & after  # the previous modules are unloaded
	assert len(after) == 1


async def test_extension_tools_join_the_sessions_that_select_them(tmp_path):
	path = _write_extension(tmp_path / "extensions", "hello", HELLO_EXTENSION)
	store = SessionStore(str(tmp_path / "data"), extension_paths=[str(path)])

	every = store.create(SessionConfig(cwd=str(tmp_path), tools=["grep"]))
	none = store.create(SessionConfig(cwd=str(tmp_path), tools=["grep"], extension_tools=[]))
	named = store.create(
		SessionConfig(cwd=str(tmp_path), tools=[], extension_tools=["hello", "gone"], auto_approve=True)
	)

	assert list(every.server_tools) == ["grep", "hello"]
	assert list(none.server_tools) == ["grep"]
	assert list(named.server_tools) == ["hello"]
	assert "- hello: Greet someone by name." in named.config.system_prompt
	assert "Greet someone" not in none.config.system_prompt
	assert named.server_tools["hello"].display_template == "Greeting {{ who }}"

	# the agent loop runs it like any tool; without arguments its display waits and its default applies
	call = AssistantMessage(content=[ToolCall(id="c1", name="hello", arguments={})])
	results = await _run_to_end(named, MockModel(replies=[call, _DONE]))
	assert results[0]["content"] == "Hello, world!"


def test_extension_routes_list_tools_and_report_diagnostics(tmp_path):
	path = _write_extension(tmp_path / "extensions", "hello", HELLO_EXTENSION)
	store = SessionStore(str(tmp_path / "data"), extension_paths=[str(path)])
	client = TestClient(create_app(store))
	builtins = [
		("bash", None, False),
		("read", None, False),
		("write", None, False),
		("edit", None, False),
		("subagent", None, False),
		("grep", None, True),
		("suggest_replies", None, True),
	]

	tools = client.get("/tools").json()["tools"]
	rows = [(t["name"], t["extension"], t["bundled"]) for t in tools]
	assert rows == [*builtins, ("hello", "hello", False)]
	assert tools[-1] == {
		"name": "hello",
		"description": "Greet someone by name.",
		"extension": "hello",
		"bundled": False,
	}
	# extension rows stay hidden while the policy switch is off
	switched_off = TestClient(create_app(store, policy=ServerPolicy(extensions=False)))
	rows = [(t["name"], t["extension"], t["bundled"]) for t in switched_off.get("/tools").json()["tools"]]
	assert rows == builtins

	created = client.post("/sessions", json={"cwd": str(tmp_path), "tools": []}).json()
	assert client.get(f"/sessions/{created['session_id']}/extensions").json() == {
		"extensions": [{"name": "hello", "path": str(path), "tools": ["hello"], "hooks": []}],
		"diagnostics": [],
	}

	path.write_text("def setup(flow):\n    raise RuntimeError('boom')\n")
	payload = client.post("/extensions/reload").json()

	assert payload["extensions"] == []
	assert any(diagnostic["severity"] == "error" for diagnostic in payload["diagnostics"])
	assert store.extension_runtime.tools == {}


def test_extension_can_override_builtin(tmp_path):
	extension = _write_extension(
		tmp_path / "extensions",
		"override",
		"""
from flow_harness.tools import ToolResult, tool

@tool
async def read(path: str, *, ctx):
    return ToolResult(content="overridden")

def setup(flow):
    flow.register_tool(read)
""",
	)
	store = SessionStore(str(tmp_path / "data"), extension_paths=[str(extension)])
	session = store.create(SessionConfig(cwd=str(tmp_path), tools=["read"]))

	assert session.server_tools["read"].func.__module__.startswith("flow_extension_override_")

	# the built-in stays listed, so a client can fall back to it by leaving the extension out
	rows = [(t["name"], t["extension"]) for t in TestClient(create_app(store)).get("/tools").json()["tools"]]
	assert rows.count(("read", None)) == 1
	assert ("read", "override") in rows
	fallback = store.create(SessionConfig(cwd=str(tmp_path), tools=["read"], extension_tools=[]))
	assert fallback.server_tools["read"].func.__module__.startswith("flow_harness.")


def test_cli_lists_extension_tools_as_json_and_load_problems_on_stderr(tmp_path, capsys):
	from types import SimpleNamespace

	from flow_harness.cli.main import _extension_tools

	folder = tmp_path / "extensions"
	missing = tmp_path / "missing.py"
	_write_extension(folder, "hello", "print('loading hello')\n" + HELLO_EXTENSION)
	broken = _write_extension(folder, "broken", "raise RuntimeError('boom')\n")

	_extension_tools(SimpleNamespace(path=[str(folder), str(missing)]))

	out, err = capsys.readouterr()
	assert json.loads(out) == {
		"tools": [{"name": "hello", "description": "Greet someone by name.", "extension": "hello"}]
	}
	assert f"flow: extension error: explicit extension path does not exist ({missing})" in err
	assert "flow: extension error: failed to import extension" in err
	assert str(broken) in err
	assert "loading hello" in err  # an extension's own output goes to stderr, not into the JSON


async def test_tool_hooks_block_rewrite_or_fail_safe(tmp_path):
	"""A raising gate blocks its call; any other faulty hook is skipped with a diagnostic and the
	result stands. In-place edits to an event never leak, and the durable call keeps the model's
	own arguments."""
	for case, event, handler, content, details, diagnostics in (
		(
			"block",
			"tool_call",
			"def handler(event):\n"
			"    if event.tool_name == 'hello':\n"
			"        return PreToolUseDecision(block=True, reason='no greetings today')\n",
			{"status": "blocked", "message": "no greetings today"},
			{},
			[],
		),
		(
			"rewrite the arguments",
			"tool_call",
			"def handler(event):\n"
			"    return PreToolUseDecision(arguments={**event.arguments, 'who': 'Rewritten'})\n",
			"Hello, Rewritten!",
			{"effective_arguments": {"who": "Rewritten"}},
			[],
		),
		(
			"rewrite the result",
			"tool_result",
			"async def handler(event):\n"
			"    content = event.result.content.replace('Flow', '[name]')\n"
			"    return PostToolUseOverride(content=content, details={'redacted': True})\n",
			"Hello, [name]!",
			{"redacted": True},
			[],
		),
		(
			"mutate the event",
			"tool_result",
			"def handler(event):\n"
			"    event.arguments['who'] = 'mutated'\n"
			"    event.result.content = 'mutated'\n"
			"    event.result.details['mutated'] = True\n",
			"Hello, Flow!",
			{},
			[],
		),
		(
			# the model learns only that the hook failed; the exception stays in diagnostics
			"raising gate",
			"tool_call",
			"def handler(event):\n    raise RuntimeError('gate crashed')\n",
			{"status": "blocked", "message": "extension `hooks` tool_call hook failed"},
			{},
			[("error", "`tool_call` handler raised")],
		),
		(
			"raising observer",
			"tool_result",
			"def handler(event):\n    raise RuntimeError('observer crashed')\n",
			"Hello, Flow!",
			{},
			[("error", "`tool_result` handler raised")],
		),
		(
			"wrong return type",
			"tool_call",
			"def handler(event):\n    return 'not a hook result'\n",
			"Hello, Flow!",
			{},
			[("warning", "unsupported result type str")],
		),
		(
			"malformed arguments",
			"tool_call",
			"def handler(event):\n    return PreToolUseDecision(arguments=42)\n",
			"Hello, Flow!",
			{},
			[("warning", "`arguments` of unsupported type int")],
		),
		(
			"malformed override",
			"tool_result",
			"def handler(event):\n    return PostToolUseOverride(content=123, details='not a dict')\n",
			"Hello, Flow!",
			{},
			[
				("warning", "`content` of unsupported type int"),
				("warning", "`details` of unsupported type str"),
			],
		),
	):
		store, session = _hook_session(tmp_path / case, event, handler)

		# two calls, so a repeating failure shows it is recorded once
		results = await _run_to_end(session, MockModel(replies=[_hello_call("c1"), _hello_call("c2"), _DONE]))

		blocked = isinstance(content, dict)
		for row in results:
			shown = json.loads(row["content"]) if blocked else row["content"]
			assert (shown, row["is_error"], row["details"]) == (content, blocked, details), case
		calls = [row for row in session.log.read_since(0) if row["type"] == "assistant_message"]
		arguments = [block["arguments"] for row in calls for block in row["content"] if "arguments" in block]
		assert arguments == [{"who": "Flow"}] * 2, case
		recorded = store.extension_runtime.diagnostics
		assert len(recorded) == len(diagnostics), case
		for diagnostic, (severity, message) in zip(recorded, diagnostics, strict=True):
			assert (diagnostic.extension, diagnostic.severity) == ("hooks", severity), case
			assert message in diagnostic.message, case


async def test_hooks_settle_a_call_before_the_approval_gate(tmp_path):
	"""The user approves the arguments that will run, and exactly those run; a blocked call is
	never put to the user; a gate that starts blocking while a run is paused still vetoes it."""
	flag = tmp_path / "block.flag"
	_, session = _hook_session(
		tmp_path,
		"tool_call",
		"from pathlib import Path\n"
		"\n"
		"def handler(event):\n"
		f"    if Path({str(flag)!r}).exists():\n"
		"        return PreToolUseDecision(block=True, reason='blocked')\n"
		"    if event.arguments['who'] == 'Flow':\n"
		"        return PreToolUseDecision(arguments={'who': 'Rewritten'})\n",
		auto_approve=False,
		confirm_tools=["hello"],
	)
	model = MockModel(replies=[_hello_call("c1"), _DONE, _hello_call("c2"), _DONE, _hello_call("c3"), _DONE])

	async def settle(handle):
		assert handle.task is not None
		await handle.task

	await settle(await session.run("go", model=model))
	approval = session.transcript.pending_approval
	assert approval is not None
	assert approval.calls[0].args == {"who": "Rewritten"}
	await settle(await session.resume({"c1": "Approve"}, model=model))

	await settle(await session.run("again", model=model))
	assert session.state.value == "paused"
	flag.touch()
	await settle(await session.resume({"c2": "Approve"}, model=model))

	await settle(await session.run("once more", model=model))
	assert session.state.value == "idle"  # blocked, not paused for approval

	results = [row for row in session.log.read_since(0) if row["type"] == "tool_result"]
	assert results[0]["content"] == "Hello, Rewritten!"
	assert [json.loads(row["content"])["message"] for row in results[1:]] == ["blocked", "blocked"]


def _hook_session(tmp_path, event: str, handler: str, **cfg):
	"""One store with the hello tool plus a hook extension that subscribes `handler` to `event`."""
	tool_path = _write_extension(tmp_path / "extensions", "hello", HELLO_EXTENSION)
	hook_path = _write_extension(
		tmp_path / "extensions",
		"hooks",
		"from flow_harness.extensions import PostToolUseOverride, PreToolUseDecision\n\n"
		f"{handler}\n"
		f"def setup(flow):\n    flow.on({event!r}, handler)\n",
	)
	store = SessionStore(str(tmp_path / "data"), extension_paths=[str(tool_path), str(hook_path)])
	session = store.create(
		SessionConfig(cwd=str(tmp_path), tools=[], auto_approve=cfg.pop("auto_approve", True), **cfg)
	)
	return store, session


def _hello_call(call_id: str) -> AssistantMessage:
	return AssistantMessage(content=[ToolCall(id=call_id, name="hello", arguments={"who": "Flow"})])


async def _run_to_end(session, model):
	handle = await session.run("go", model=model)
	assert handle.task is not None
	await handle.task
	return [row for row in session.log.read_since(0) if row["type"] == "tool_result"]
