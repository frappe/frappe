"""Extension discovery, loading, and tool integration."""

from pathlib import Path

from fastapi.testclient import TestClient

from flow import config as server_config
from flow.events import AssistantMessage, ToolCall
from flow.extensions import ExtensionRuntime
from flow.extensions.loader import discover_extensions
from flow.model.mock import MockModel
from flow.server import create_app
from flow.session.config import SessionConfig
from flow.session.store import SessionStore
from flow.tools import ToolContext

HELLO_EXTENSION = """
from flow.tools import ToolResult, tool

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
		"from flow.tools import ToolResult, tool\n"
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


def test_extension_diagnostics_endpoint(tmp_path):
	extension = _write_extension(tmp_path / "extensions", "hello", HELLO_EXTENSION)
	store = SessionStore(str(tmp_path / "data"), extension_paths=[str(extension)])
	client = TestClient(create_app(store))
	created = client.post("/sessions", json={"cwd": str(tmp_path), "tools": []}).json()

	payload = client.get(f"/sessions/{created['session_id']}/extensions").json()

	assert payload["extensions"] == [{"name": "hello", "path": str(extension), "tools": ["hello"]}]
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
from flow.tools import ToolResult, tool

@tool
async def read_file(path: str, *, ctx):
    return ToolResult(content="overridden")

def setup(flow):
    flow.register_tool(read_file)
""",
	)
	store = SessionStore(str(tmp_path / "data"), extension_paths=[str(extension)])
	session = store.create(SessionConfig(cwd=str(tmp_path), tools=["read_file"]))

	assert session.server_tools["read_file"].func.__module__.startswith("flow_extension_override_")


def test_cli_reports_extension_diagnostics_on_stderr(tmp_path, capsys):
	from flow.cli.main import _report_extension_diagnostics

	missing = tmp_path / "missing.py"
	broken = _write_extension(tmp_path / "extensions", "broken", "raise RuntimeError('boom')\n")
	store = SessionStore(str(tmp_path / "data"), extension_paths=[str(missing), str(broken)])

	_report_extension_diagnostics(store)

	stderr = capsys.readouterr().err
	assert f"flow: extension error: explicit extension path does not exist ({missing})" in stderr
	assert "flow: extension error: failed to import extension" in stderr
	assert str(broken) in stderr


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
