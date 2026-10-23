"""Bundled tools: off by default, selectable by name, and the tools themselves."""

import importlib

import pytest

from flow_harness.session.config import SessionConfig
from flow_harness.session.store import SessionStore
from flow_harness.tools.bundled.grep import grep
from flow_harness.tools.bundled.suggest_replies import suggest_replies
from flow_harness.tools.tool import ToolContext


def _ctx(tmp_path, **kw) -> ToolContext:
	return ToolContext(cwd=str(tmp_path), **kw)


@pytest.fixture(params=[True, False], ids=["ripgrep", "grep"])
def engine(request, monkeypatch):
	"""Run once on ripgrep (when installed) and once on the grep fallback."""
	grep_module = importlib.import_module("flow_harness.tools.bundled.grep")
	rg = grep_module.shutil.which("rg")
	if request.param and rg is None:
		pytest.skip("ripgrep is not installed")
	monkeypatch.setattr(grep_module.shutil, "which", lambda _name: rg if request.param else None)


def test_bundled_tools_are_off_unless_named(tmp_path):
	store = SessionStore(str(tmp_path / "data"))
	default = store.create(SessionConfig(cwd=str(tmp_path)))
	assert not {"grep", "suggest_replies"} & set(default.server_tools)
	assert "- grep: " not in default.config.system_prompt

	named = store.create(SessionConfig(cwd=str(tmp_path), tools=["read", "grep", "suggest_replies"]))
	assert list(named.server_tools) == ["read", "grep", "suggest_replies"]
	assert "- grep: " in named.config.system_prompt


async def test_suggest_replies_hands_the_client_its_checked_replies(tmp_path):
	shown = await suggest_replies(replies=[" Yes ", "No"], multi_select=True, ctx=_ctx(tmp_path))
	assert not shown.is_error
	assert shown.details == {"replies": ["Yes", "No"], "multi_select": True}
	for replies in (["Only"], ["a", "b", "c", "d", "e"], ["Yes", " "], ["Yes", "Yes "]):
		refused = await suggest_replies(replies=replies, ctx=_ctx(tmp_path))
		assert refused.is_error and refused.details == {}, replies


async def test_grep_search_skips_and_filters(tmp_path, engine):
	(tmp_path / "sub").mkdir()
	for name in ("a.py", "b.js", "sub/c.vue"):
		(tmp_path / name).write_text("needle\n")
	(tmp_path / "node_modules" / "pkg").mkdir(parents=True)
	(tmp_path / "node_modules" / "pkg" / "x.py").write_text("needle\n")
	(tmp_path / "blob.bin").write_bytes(b"needle\0\x01")
	(tmp_path / "words.txt").write_text("alpha\nbeta\ngamma\n")
	ctx = _ctx(tmp_path)

	for case, kwargs, matches, shown, absent in (
		# node_modules and binary files are skipped
		("default", {"pattern": "needle"}, 3, ["a.py", "b.js", "c.vue"], ["node_modules", "blob"]),
		("include", {"pattern": "needle", "include": "**/*.{py,vue}"}, 2, ["a.py", "c.vue"], ["b.js"]),
		("pointed at node_modules", {"pattern": "needle", "path": "node_modules"}, 1, ["x.py"], []),
		# plain grep's default basic regex reads `|` as a literal and finds nothing
		("extended regex", {"pattern": "alpha|beta"}, 2, ["alpha", "beta"], ["gamma"]),
		("no match", {"pattern": "zzz-nomatch-zzz"}, 0, ["[no matches]"], []),
	):
		result = await grep(**kwargs, ctx=ctx)
		assert not result.is_error, case
		assert result.details["matches"] == matches, case
		assert all(text in result.content for text in shown), case
		assert not any(text in result.content for text in absent), case

	refused = await grep(pattern="needle", include="*.{spec,test}.{js,ts}", ctx=ctx)
	assert refused.is_error
	assert "one {a,b} group" in refused.content


async def test_grep_stays_inside_the_allowed_root(tmp_path, monkeypatch, engine):
	allowed = tmp_path / "allowed"
	outside = tmp_path / "outside"
	(allowed / ".private").mkdir(parents=True)
	outside.mkdir()
	(allowed / "a.py").write_text("needle\n")
	(allowed / "visible.txt").write_text("needle visible\n")
	(allowed / "dash.txt").write_text("-L is a literal here\n")
	(allowed / ".secret").write_text("needle hidden\n")
	(allowed / ".secret.py").write_text("needle\n")
	(allowed / ".private" / "x.py").write_text("needle\n")
	(outside / "secret.txt").write_text("SUPER-SECRET\n")
	monkeypatch.chdir(outside)  # where a pattern read as a flag would search instead
	ctx = _ctx(allowed, allowed_roots=(str(allowed),), ignore_hidden_files=True)

	with pytest.raises(PermissionError, match="outside the configured allowed roots"):
		await grep(pattern="secret", path="..", ctx=ctx)
	for case, kwargs, matches, shown in (
		("hidden files", {"pattern": "needle"}, 2, "visible.txt"),
		# an include placed after the hidden-file skips would win and search `.secret.py`
		("include", {"pattern": "needle", "include": "*.py"}, 1, "a.py"),
		# an unseparated pattern would be read as a flag, dropping the search path
		("-L", {"pattern": "-L", "path": "."}, 1, "-L is a literal here"),
		("-l", {"pattern": "-l", "path": "."}, 0, "[no matches]"),
		("-r", {"pattern": "-r", "path": "."}, 0, "[no matches]"),
	):
		result = await grep(**kwargs, ctx=ctx)
		assert result.details["matches"] == matches, case
		assert shown in result.content, case
		for text in (".private", ".secret", "secret.txt", "SUPER-SECRET"):
			assert text not in result.content, (case, text)


async def test_grep_stops_reading_a_flood_of_matches(tmp_path):
	"""A catch-all pattern over a big tree must not be buffered whole: 3 GB of it once froze the daemon."""
	(tmp_path / "big.txt").write_text("match line\n" * 400_000)
	ctx = _ctx(tmp_path)

	result = await grep(pattern=".", path=".", ctx=ctx)

	assert result.content.endswith("+ match lines]")
	assert 0 < result.details["matches"] < 400_000
	assert result.details["truncation"]["output_lines"] <= 2000
