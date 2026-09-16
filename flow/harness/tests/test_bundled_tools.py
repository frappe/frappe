"""Bundled tools: off by default, selectable by name, and the grep tool itself."""

import importlib

import pytest
from fastapi.testclient import TestClient

from flow_harness.server import create_app
from flow_harness.session.config import SessionConfig
from flow_harness.session.store import SessionStore
from flow_harness.tools import BUILTIN_TOOLS, BUNDLED_TOOLS
from flow_harness.tools.bundled.grep import grep
from flow_harness.tools.tool import ToolContext


def _ctx(tmp_path, **kw) -> ToolContext:
	return ToolContext(cwd=str(tmp_path), **kw)


def test_registry_keys():
	assert set(BUNDLED_TOOLS) == {"grep"}
	assert not set(BUNDLED_TOOLS) & set(BUILTIN_TOOLS)


def test_bundled_tools_are_off_unless_named(tmp_path):
	store = SessionStore(str(tmp_path / "data"))
	default = store.create(SessionConfig(cwd=str(tmp_path)))
	assert "grep" not in default.server_tools
	assert "- grep: " not in default.config.system_prompt

	named = store.create(SessionConfig(cwd=str(tmp_path), tools=["read", "grep"]))
	assert list(named.server_tools) == ["read", "grep"]
	assert "- grep: " in named.config.system_prompt


def test_tools_route_flags_bundled_tools(tmp_path):
	client = TestClient(create_app(SessionStore(str(tmp_path / "data"))))
	bundled = {t["name"]: t["bundled"] for t in client.get("/tools").json()["tools"]}
	assert bundled == {
		"bash": False,
		"read": False,
		"write": False,
		"edit": False,
		"grep": True,
	}


async def test_grep_rejects_traversal_outside_allowed_roots(tmp_path):
	allowed = tmp_path / "allowed"
	allowed.mkdir()
	(tmp_path / "outside.txt").write_text("secret")
	ctx = _ctx(allowed, allowed_roots=(str(allowed),))
	with pytest.raises(PermissionError, match="outside the configured allowed roots"):
		await grep(pattern="secret", path="..", ctx=ctx)


@pytest.mark.parametrize("use_ripgrep", [True, False], ids=["ripgrep", "grep"])
async def test_hidden_paths_can_be_ignored(tmp_path, monkeypatch, use_ripgrep):
	(tmp_path / "visible.txt").write_text("needle visible")
	hidden_dir = tmp_path / ".private"
	hidden_dir.mkdir()
	(hidden_dir / "secret.txt").write_text("needle hidden")
	(tmp_path / ".secret").write_text("needle hidden")
	ctx = _ctx(tmp_path, allowed_roots=(str(tmp_path),), ignore_hidden_files=True)

	grep_module = importlib.import_module("flow_harness.tools.bundled.grep")
	rg = grep_module.shutil.which("rg")
	if use_ripgrep and rg is None:
		pytest.skip("ripgrep is not installed")
	monkeypatch.setattr(grep_module.shutil, "which", lambda _name: rg if use_ripgrep else None)
	result = await grep(pattern="needle", ctx=ctx)
	assert "visible.txt" in result.content
	assert ".private" not in result.content
	assert ".secret" not in result.content


async def test_grep_finds_and_misses(tmp_path):
	(tmp_path / "a.txt").write_text("needle here\nother line")
	ctx = _ctx(tmp_path)
	found = await grep(pattern="needle", path=".", ctx=ctx)
	assert "needle" in found.content
	assert found.details["matches"] == 1
	miss = await grep(pattern="zzz-nomatch-zzz", path=".", ctx=ctx)
	assert miss.content == "[no matches]"
	assert miss.details["matches"] == 0


async def test_grep_stops_reading_a_flood_of_matches(tmp_path):
	"""A catch-all pattern over a big tree must not be buffered whole: 3 GB of it once froze the daemon."""
	(tmp_path / "big.txt").write_text("match line\n" * 400_000)
	ctx = _ctx(tmp_path)

	result = await grep(pattern=".", path=".", ctx=ctx)

	assert result.content.endswith("+ match lines]")
	assert 0 < result.details["matches"] < 400_000
	assert result.details["truncation"]["output_lines"] <= 2000


async def test_grep_treats_an_option_like_pattern_as_a_pattern(tmp_path):
	"""An unseparated pattern would be read as a flag, dropping the search path."""
	allowed = tmp_path / "allowed"
	allowed.mkdir()
	(allowed / "a.txt").write_text("-L is a literal here\n")
	ctx = _ctx(allowed, allowed_roots=(str(allowed),))

	found = await grep(pattern="-L", path=".", ctx=ctx)

	assert "-L is a literal here" in found.content
	assert found.details["matches"] == 1


async def test_grep_option_like_pattern_cannot_search_outside_the_root(tmp_path, monkeypatch):
	allowed = tmp_path / "allowed"
	outside = tmp_path / "outside"
	allowed.mkdir()
	outside.mkdir()
	(outside / "secret.txt").write_text("SUPER-SECRET\n")
	monkeypatch.chdir(outside)  # a bare recursive search would land here
	ctx = _ctx(allowed, allowed_roots=(str(allowed),))

	for pattern in ("-L", "-l", "-r"):
		result = await grep(pattern=pattern, path=".", ctx=ctx)
		assert "secret.txt" not in result.content
		assert "SUPER-SECRET" not in result.content
