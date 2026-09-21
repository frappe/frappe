"""Extension discovery, loading, tool integration, and tool hooks."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from flow_harness import config as server_config
from flow_harness.events import AssistantMessage, ToolCall
from flow_harness.extensions import ExtensionRuntime
from flow_harness.extensions.loader import discover_extensions
from flow_harness.model.mock import MockModel
from flow_harness.server import create_app
from flow_harness.server.policy import ServerPolicy
from flow_harness.session.config import SessionConfig
from flow_harness.session.store import SessionStore
from flow_harness.tools import ToolContext

HELLO_EXTENSION = """
from flow_harness.tools import ToolResult, tool

@tool(prompt_snippet="Greet someone by name.", display_template="Greeting {{ who }}")
async def hello(who: str = "world", *, ctx):
    return ToolResult(content=f"Hello, {who}!")

def setup(flow):
    flow.register_tool(hello)
"""


def _write_extension(directory: Path, name: str, body: str) -> Path:
	directory.mkdir(parents=True, exist_ok=True)
	path = directory / f"{name}.py"
	path.write_text(body)
	return path


def test_discovers_user_and_explicit_extensions(tmp_path):
	global_dir = tmp_path / "home" / "extensions"
	explicit = _write_extension(tmp_path / "elsewhere", "explicit", "def setup(flow):\n    pass\n")
	_write_extension(global_dir, "global_ext", "def setup(flow):\n    pass\n")

	discovered, diagnostics = discover_extensions(global_dir=global_dir, extra_paths=(explicit,))

	assert [extension.name for extension in discovered] == ["global_ext", "explicit"]
	assert diagnostics == ()


def test_broken_extension_does_not_block_other_extensions(tmp_path):
	global_dir = tmp_path / "extensions"
	_write_extension(global_dir, "broken", "raise RuntimeError('boom')\n")
	_write_extension(global_dir, "hello", HELLO_EXTENSION)
	runtime = ExtensionRuntime()

	runtime.load(global_dir=global_dir)

	assert [extension.name for extension in runtime.extensions] == ["hello"]
	assert list(runtime.tools) == ["hello"]
	assert any(diagnostic.extension == "broken" for diagnostic in runtime.diagnostics)


def test_directory_extension_uses_relative_imports(tmp_path):
	package = tmp_path / "extensions" / "greeter"
	package.mkdir(parents=True)
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
	runtime = ExtensionRuntime()

	runtime.load(global_dir=tmp_path / "extensions")

	assert [extension.name for extension in runtime.extensions] == ["greeter"]
	assert list(runtime.tools) == ["greet"]
	assert runtime.diagnostics == ()


def test_store_skips_global_dir_unless_enabled(tmp_path, monkeypatch):
	_write_extension(tmp_path / "global", "hello", HELLO_EXTENSION)
	monkeypatch.setattr(server_config, "EXTENSIONS_PATH", str(tmp_path / "global"))

	assert SessionStore(str(tmp_path / "data")).extension_runtime.tools == {}
	enabled = SessionStore(str(tmp_path / "data2"), extensions_enabled=True)
	assert list(enabled.extension_runtime.tools) == ["hello"]


async def test_extension_tool_executes_with_normal_context(tmp_path):
	extension = _write_extension(tmp_path / "extensions", "hello", HELLO_EXTENSION)
	store = SessionStore(str(tmp_path / "data"), extension_paths=[str(extension)])
	session = store.create(SessionConfig(cwd=str(tmp_path), tools=[], auto_approve=True))
	tool = session.server_tools["hello"]
	assert tool.display_template == "Greeting {{ who }}"

	result = await tool(who="Flow", ctx=ToolContext(cwd=str(tmp_path)))

	assert result.content == "Hello, Flow!"
	assert "- hello: Greet someone by name." in session.config.system_prompt


async def test_extension_tool_is_available_to_agent_loop(tmp_path):
	extension = _write_extension(tmp_path / "extensions", "hello", HELLO_EXTENSION)
	store = SessionStore(str(tmp_path / "data"), extension_paths=[str(extension)])
	session = store.create(SessionConfig(cwd=str(tmp_path), tools=[], auto_approve=True))
	model = MockModel(
		replies=[
			AssistantMessage(content=[ToolCall(id="hello-1", name="hello", arguments={"who": "Flow"})]),
			AssistantMessage(content="done"),
		]
	)

	handle = await session.run("say hello", model=model)
	assert handle.task is not None
	await handle.task

	results = [row for row in session.log.read_since(0) if row["type"] == "tool_result"]
	assert results[0]["content"] == "Hello, Flow!"


def test_extension_tools_can_be_selected_per_session(tmp_path):
	path = _write_extension(tmp_path / "extensions", "hello", HELLO_EXTENSION)
	store = SessionStore(str(tmp_path / "data"), extension_paths=[str(path)])

	every = store.create(SessionConfig(cwd=str(tmp_path), tools=["grep"]))
	none = store.create(SessionConfig(cwd=str(tmp_path), tools=["grep"], extension_tools=[]))
	named = store.create(SessionConfig(cwd=str(tmp_path), tools=[], extension_tools=["hello", "gone"]))

	assert list(every.server_tools) == ["grep", "hello"]
	assert list(none.server_tools) == ["grep"]
	assert list(named.server_tools) == ["hello"]
	assert "Greet someone" in named.config.system_prompt
	assert "Greet someone" not in none.config.system_prompt


def test_tools_route_lists_extension_tools_with_their_source(tmp_path):
	path = _write_extension(tmp_path / "extensions", "hello", HELLO_EXTENSION)
	store = SessionStore(str(tmp_path / "data"), extension_paths=[str(path)])
	client = TestClient(create_app(store))

	tools = client.get("/tools").json()["tools"]

	assert [t["name"] for t in tools] == [
		"bash",
		"read",
		"write",
		"edit",
		"subagent",
		"grep",
		"hello",
	]
	assert tools[-1] == {
		"name": "hello",
		"description": "Greet someone by name.",
		"extension": "hello",
		"bundled": False,
	}
	assert all(t["extension"] is None for t in tools[:-1])


def test_tools_route_hides_extension_tools_when_the_policy_switch_is_off(tmp_path):
	path = _write_extension(tmp_path / "extensions", "hello", HELLO_EXTENSION)
	store = SessionStore(str(tmp_path / "data"), extension_paths=[str(path)])
	client = TestClient(create_app(store, policy=ServerPolicy(extensions=False)))

	tools = client.get("/tools").json()["tools"]

	assert [t["name"] for t in tools] == ["bash", "read", "write", "edit", "subagent", "grep"]


def test_extension_diagnostics_endpoint(tmp_path):
	extension = _write_extension(tmp_path / "extensions", "hello", HELLO_EXTENSION)
	store = SessionStore(str(tmp_path / "data"), extension_paths=[str(extension)])
	client = TestClient(create_app(store))
	created = client.post("/sessions", json={"cwd": str(tmp_path), "tools": []}).json()

	payload = client.get(f"/sessions/{created['session_id']}/extensions").json()

	assert payload["extensions"] == [
		{"name": "hello", "path": str(extension), "tools": ["hello"], "hooks": []}
	]
	assert payload["diagnostics"] == []


def test_extensions_load_once_per_store(tmp_path):
	marker = tmp_path / "loads.txt"
	extension = _write_extension(
		tmp_path / "extensions",
		"counter",
		f"""
from pathlib import Path
with Path({str(marker)!r}).open("a") as f:
    f.write("x")
def setup(flow):
    pass
""",
	)
	store = SessionStore(str(tmp_path / "data"), extension_paths=[str(extension)])

	store.create(SessionConfig(cwd=str(tmp_path), tools=[]))
	store.create(SessionConfig(cwd=str(tmp_path), tools=[]))

	assert marker.read_text() == "x"


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


def test_cli_reports_extension_diagnostics_on_stderr(tmp_path, capsys):
	from flow_harness.cli.main import _report_extension_diagnostics

	missing = tmp_path / "missing.py"
	broken = _write_extension(tmp_path / "extensions", "broken", "raise RuntimeError('boom')\n")
	store = SessionStore(str(tmp_path / "data"), extension_paths=[str(missing), str(broken)])

	_report_extension_diagnostics(store.extension_runtime)

	stderr = capsys.readouterr().err
	assert f"flow: extension error: explicit extension path does not exist ({missing})" in stderr
	assert "flow: extension error: failed to import extension" in stderr
	assert str(broken) in stderr


def test_cli_lists_the_tools_extensions_register_as_json(tmp_path, capsys):
	from types import SimpleNamespace

	from flow_harness.cli.main import _extension_tools

	folder = tmp_path / "extensions"
	_write_extension(folder, "hello", HELLO_EXTENSION)
	_write_extension(folder, "broken", "raise RuntimeError('boom')\n")

	_extension_tools(SimpleNamespace(path=[str(folder)]))

	out, err = capsys.readouterr()
	assert json.loads(out) == {
		"tools": [{"name": "hello", "description": "Greet someone by name.", "extension": "hello"}]
	}
	assert "flow: extension error: failed to import extension" in err


def _hook_session(tmp_path, hook_body: str, **cfg):
	"""One store with the hello tool plus a hook extension, and a session over them."""
	tool_path = _write_extension(tmp_path / "extensions", "hello", HELLO_EXTENSION)
	hook_path = _write_extension(tmp_path / "extensions", "hooks", hook_body)
	store = SessionStore(str(tmp_path / "data"), extension_paths=[str(tool_path), str(hook_path)])
	session = store.create(
		SessionConfig(cwd=str(tmp_path), tools=[], auto_approve=cfg.pop("auto_approve", True), **cfg)
	)
	return store, session


def _hello_call_model(who="Flow"):
	return MockModel(
		replies=[
			AssistantMessage(content=[ToolCall(id="c1", name="hello", arguments={"who": who})]),
			AssistantMessage(content="done"),
		]
	)


async def _run_to_end(session, model):
	handle = await session.run("go", model=model)
	assert handle.task is not None
	await handle.task
	return [row for row in session.log.read_since(0) if row["type"] == "tool_result"]


async def test_tool_call_hook_blocks_a_call(tmp_path):
	store, session = _hook_session(
		tmp_path,
		"""
from flow_harness.extensions import PreToolUseDecision

def gate(event):
    if event.tool_name == "hello":
        return PreToolUseDecision(block=True, reason="no greetings today")
    return None

def setup(flow):
    flow.on("tool_call", gate)
""",
	)

	results = await _run_to_end(session, _hello_call_model())

	assert results[0]["is_error"] is True
	assert json.loads(results[0]["content"]) == {"status": "blocked", "message": "no greetings today"}
	assert store.extension_runtime.diagnostics == ()


async def test_tool_call_hook_rewrites_arguments(tmp_path):
	_, session = _hook_session(
		tmp_path,
		"""
from flow_harness.extensions import PreToolUseDecision

def rewrite(event):
    return PreToolUseDecision(arguments={**event.arguments, "who": "Rewritten"})

def setup(flow):
    flow.on("tool_call", rewrite)
""",
	)

	results = await _run_to_end(session, _hello_call_model())

	assert results[0]["content"] == "Hello, Rewritten!"
	assert results[0]["details"]["effective_arguments"] == {"who": "Rewritten"}
	# the durable tool call keeps the model's original arguments
	calls = [row for row in session.log.read_since(0) if row["type"] == "assistant_message"]
	assert calls[0]["content"][0]["arguments"] == {"who": "Flow"}


async def test_tool_result_hook_rewrites_content_and_details(tmp_path):
	_, session = _hook_session(
		tmp_path,
		"""
from flow_harness.extensions import PostToolUseOverride

async def redact(event):
    return PostToolUseOverride(content=event.result.content.replace("Flow", "[name]"), details={"redacted": True})

def setup(flow):
    flow.on("tool_result", redact)
""",
	)

	results = await _run_to_end(session, _hello_call_model())

	assert results[0]["content"] == "Hello, [name]!"
	assert results[0]["details"] == {"redacted": True}


async def test_failing_tool_call_hook_blocks_and_records_one_diagnostic(tmp_path):
	store, session = _hook_session(
		tmp_path,
		"""
def broken(event):
    raise RuntimeError("gate crashed")

def setup(flow):
    flow.on("tool_call", broken)
""",
	)
	model = MockModel(
		replies=[
			AssistantMessage(content=[ToolCall(id="c1", name="hello", arguments={})]),
			AssistantMessage(content=[ToolCall(id="c2", name="hello", arguments={})]),
			AssistantMessage(content="done"),
		]
	)

	results = await _run_to_end(session, model)

	assert all(row["is_error"] for row in results)
	assert "hook failed" in json.loads(results[0]["content"])["message"]
	# the exception text stays in diagnostics; the model only learns the hook failed
	assert "gate crashed" not in results[0]["content"]
	diagnostics = [d for d in store.extension_runtime.diagnostics if d.extension == "hooks"]
	assert len(diagnostics) == 1  # the repeating failure is recorded once
	assert diagnostics[0].severity == "error"
	assert "`tool_call` handler raised" in diagnostics[0].message


async def test_malformed_decision_fields_are_ignored_with_warnings(tmp_path):
	"""A well-typed decision with garbage fields degrades per field — never a dead run."""
	store, session = _hook_session(
		tmp_path,
		"""
from flow_harness.extensions import PreToolUseDecision, PostToolUseOverride

def bad_arguments(event):
    return PreToolUseDecision(arguments=42)

def bad_override(event):
    return PostToolUseOverride(content=123, details="not a dict")

def setup(flow):
    flow.on("tool_call", bad_arguments)
    flow.on("tool_result", bad_override)
""",
	)

	results = await _run_to_end(session, _hello_call_model())

	assert results[0]["content"] == "Hello, Flow!"  # original args ran, result stands
	assert results[0]["is_error"] is False
	messages = [d.message for d in store.extension_runtime.diagnostics if d.severity == "warning"]
	assert any("`arguments` of unsupported type int" in m for m in messages)
	assert any("`content` of unsupported type int" in m for m in messages)
	assert any("`details` of unsupported type str" in m for m in messages)


async def test_mutating_hook_events_does_not_touch_the_transcript(tmp_path):
	"""In-place edits to hook events must not leak; returning a result is the only channel."""
	_, session = _hook_session(
		tmp_path,
		"""
def mutate(event):
    event.arguments["who"] = "mutated"
    event.result.content = "mutated"
    event.result.details["mutated"] = True
    return None

def setup(flow):
    flow.on("tool_result", mutate)
""",
	)

	results = await _run_to_end(session, _hello_call_model())

	assert results[0]["content"] == "Hello, Flow!"
	assert results[0]["details"] == {}
	calls = [row for row in session.log.read_since(0) if row["type"] == "assistant_message"]
	assert calls[0]["content"][0]["arguments"] == {"who": "Flow"}


async def test_failing_tool_result_hook_keeps_the_result(tmp_path):
	store, session = _hook_session(
		tmp_path,
		"""
def broken(event):
    raise RuntimeError("observer crashed")

def setup(flow):
    flow.on("tool_result", broken)
""",
	)

	results = await _run_to_end(session, _hello_call_model())

	assert results[0]["content"] == "Hello, Flow!"
	assert results[0]["is_error"] is False
	assert any("`tool_result` handler raised" in d.message for d in store.extension_runtime.diagnostics)


async def test_bad_hook_return_type_is_ignored_with_a_warning(tmp_path):
	store, session = _hook_session(
		tmp_path,
		"""
def bad(event):
    return "not a hook result"

def setup(flow):
    flow.on("tool_call", bad)
""",
	)

	results = await _run_to_end(session, _hello_call_model())

	assert results[0]["content"] == "Hello, Flow!"
	diagnostic = next(d for d in store.extension_runtime.diagnostics if d.extension == "hooks")
	assert diagnostic.severity == "warning"
	assert "unsupported result type str" in diagnostic.message


async def test_blocking_hook_preempts_the_confirm_gate(tmp_path):
	"""A blocked call is settled before the gate — the user is never asked to approve it."""
	_, session = _hook_session(
		tmp_path,
		"""
from flow_harness.extensions import PreToolUseDecision

def gate(event):
    return PreToolUseDecision(block=True, reason="never reaches approval")

def setup(flow):
    flow.on("tool_call", gate)
""",
		auto_approve=False,
		confirm_tools=["hello"],
	)

	results = await _run_to_end(session, _hello_call_model())

	assert session.state.value == "idle"  # blocked, not paused for approval
	assert json.loads(results[0]["content"])["message"] == "never reaches approval"


async def test_rewritten_arguments_reach_the_approval_prompt(tmp_path):
	"""The user approves the effective arguments, and exactly those run."""
	_, session = _hook_session(
		tmp_path,
		"""
from flow_harness.extensions import PreToolUseDecision

def rewrite(event):
    return PreToolUseDecision(arguments={"who": "Rewritten"})

def setup(flow):
    flow.on("tool_call", rewrite)
""",
		auto_approve=False,
		confirm_tools=["hello"],
	)
	model = _hello_call_model()

	handle = await session.run("go", model=model)
	assert handle.task is not None
	await handle.task
	approval = session.transcript.pending_approval
	assert approval is not None
	assert approval.calls[0].args == {"who": "Rewritten"}
	resumed = await session.resume({"c1": "Approve"}, model=model)
	assert resumed.task is not None
	await resumed.task

	results = [row for row in session.log.read_since(0) if row["type"] == "tool_result"]
	assert results[0]["content"] == "Hello, Rewritten!"


async def test_resume_re_checks_blocking(tmp_path):
	"""A gate that starts blocking while a run is paused still vetoes the approved call."""
	flag = tmp_path / "block.flag"
	_, session = _hook_session(
		tmp_path,
		f"""
from pathlib import Path
from flow_harness.extensions import PreToolUseDecision

def gate(event):
    if Path({str(flag)!r}).exists():
        return PreToolUseDecision(block=True, reason="blocked at resume")
    return None

def setup(flow):
    flow.on("tool_call", gate)
""",
		auto_approve=False,
		confirm_tools=["hello"],
	)
	model = _hello_call_model()

	handle = await session.run("go", model=model)
	assert handle.task is not None
	await handle.task
	assert session.state.value == "paused"
	flag.touch()
	resumed = await session.resume({"c1": "Approve"}, model=model)
	assert resumed.task is not None
	await resumed.task

	results = [row for row in session.log.read_since(0) if row["type"] == "tool_result"]
	assert json.loads(results[0]["content"])["message"] == "blocked at resume"


def test_unknown_hook_event_fails_setup_with_a_diagnostic(tmp_path):
	path = _write_extension(
		tmp_path / "extensions",
		"bad_event",
		"def setup(flow):\n    flow.on('turn_start', lambda event: None)\n",
	)
	runtime = ExtensionRuntime()

	runtime.load(global_dir=None, extra_paths=(path,))

	assert runtime.extensions == ()
	diagnostic = runtime.diagnostics[0]
	assert diagnostic.severity == "error"
	assert "unknown hook event" in diagnostic.message


def test_info_lists_hook_subscriptions(tmp_path):
	path = _write_extension(
		tmp_path / "extensions",
		"gate",
		"""
def setup(flow):
    flow.on("tool_call", lambda event: None)
    flow.on("tool_result", lambda event: None)
""",
	)
	runtime = ExtensionRuntime()

	runtime.load(global_dir=None, extra_paths=(path,))

	assert runtime.info()["extensions"][0]["hooks"] == ["tool_call", "tool_result"]


def test_reload_swaps_tools_for_store_and_cached_sessions(tmp_path):
	path = _write_extension(tmp_path / "extensions", "hello", HELLO_EXTENSION)
	store = SessionStore(str(tmp_path / "data"), extension_paths=[str(path)])
	session = store.create(SessionConfig(cwd=str(tmp_path), tools=[]))
	assert list(session.server_tools) == ["hello"]

	path.write_text(HELLO_EXTENSION.replace("hello", "howdy_tool"))
	store.reload_extensions()

	assert list(store.extension_runtime.tools) == ["howdy_tool"]
	assert list(session.server_tools) == ["howdy_tool"]
	assert store.extension_runtime.diagnostics == ()


def test_reload_unloads_previous_extension_modules(tmp_path):
	import sys

	path = _write_extension(tmp_path / "extensions", "hello", HELLO_EXTENSION)
	store = SessionStore(str(tmp_path / "data"), extension_paths=[str(path)])
	before = {name for name in sys.modules if name.startswith("flow_extension_")}

	store.reload_extensions()

	after = {name for name in sys.modules if name.startswith("flow_extension_")}
	assert not before & after
	assert len(after) == 1


def test_reload_endpoint_reports_fresh_diagnostics(tmp_path):
	path = _write_extension(tmp_path / "extensions", "hello", HELLO_EXTENSION)
	store = SessionStore(str(tmp_path / "data"), extension_paths=[str(path)])
	client = TestClient(create_app(store))
	path.write_text("def setup(flow):\n    raise RuntimeError('boom')\n")

	payload = client.post("/extensions/reload").json()

	assert payload["extensions"] == []
	assert any(diagnostic["severity"] == "error" for diagnostic in payload["diagnostics"])
	assert store.extension_runtime.tools == {}
