import asyncio
import inspect
import os

import pytest

from flow.tools.builtins import BUILTIN_TOOLS, bash, edit, grep, read_file, write
from flow.tools.tool import ToolContext, ToolResult


def _ctx(tmp_path, **kw) -> ToolContext:
	return ToolContext(cwd=str(tmp_path), **kw)


def test_registry_keys():
	assert set(BUILTIN_TOOLS) == {"bash", "read_file", "write", "edit", "grep"}
	assert BUILTIN_TOOLS["bash"].requires_confirmation is True
	assert BUILTIN_TOOLS["read_file"].requires_confirmation is False


async def test_write_then_read_roundtrip(tmp_path):
	ctx = _ctx(tmp_path)
	res = await write(path="sub/note.txt", content="hello", ctx=ctx)
	assert isinstance(res, ToolResult)
	assert "wrote sub/note.txt" in res.content
	assert res.details == {"path": str(tmp_path / "sub" / "note.txt"), "chars": 5}
	assert (tmp_path / "sub" / "note.txt").read_text() == "hello"
	assert (await read_file(path="sub/note.txt", ctx=ctx)).content == "hello"


async def test_path_tools_reject_traversal_outside_allowed_roots(tmp_path):
	allowed = tmp_path / "allowed"
	allowed.mkdir()
	outside = tmp_path / "outside.txt"
	outside.write_text("secret")
	ctx = _ctx(allowed, allowed_roots=(str(allowed),))

	for call in (
		read_file(path="../outside.txt", ctx=ctx),
		write(path="../created.txt", content="nope", ctx=ctx),
		edit(path="../outside.txt", edits=[{"old": "secret", "new": "changed"}], ctx=ctx),
		grep(pattern="secret", path="..", ctx=ctx),
	):
		with pytest.raises(PermissionError, match="outside the configured allowed roots"):
			await call

	assert outside.read_text() == "secret"
	assert not (tmp_path / "created.txt").exists()


async def test_path_tools_reject_symlink_escape(tmp_path):
	allowed = tmp_path / "allowed"
	outside = tmp_path / "outside"
	allowed.mkdir()
	outside.mkdir()
	(outside / "secret.txt").write_text("secret")
	(allowed / "link").symlink_to(outside, target_is_directory=True)
	ctx = _ctx(allowed, allowed_roots=(str(allowed),))

	with pytest.raises(PermissionError, match="outside the configured allowed roots"):
		await read_file(path="link/secret.txt", ctx=ctx)
	with pytest.raises(PermissionError, match="outside the configured allowed roots"):
		await write(path="link/new.txt", content="nope", ctx=ctx)

	assert not (outside / "new.txt").exists()


async def test_path_tools_preserve_addressed_path_for_allowed_symlink(tmp_path):
	allowed = tmp_path / "allowed"
	target = allowed / "target"
	allowed.mkdir()
	target.mkdir()
	(target / "note.txt").write_text("hello")
	(allowed / "link").symlink_to(target, target_is_directory=True)
	ctx = _ctx(allowed, allowed_roots=(str(allowed),))

	result = await read_file(path="link/note.txt", ctx=ctx)

	assert result.content == "hello"
	assert result.details["path"] == str(allowed / "link" / "note.txt")


async def test_path_tools_allow_any_configured_root(tmp_path):
	project = tmp_path / "project"
	shared = tmp_path / "shared"
	project.mkdir()
	shared.mkdir()
	(shared / "context.txt").write_text("shared context")
	ctx = _ctx(project, allowed_roots=(str(project), str(shared)))

	result = await read_file(path=str(shared / "context.txt"), ctx=ctx)

	assert result.content == "shared context"


async def test_read_missing_file(tmp_path):
	res = await read_file(path="nope.txt", ctx=_ctx(tmp_path))
	assert res.is_error
	assert "no such file" in res.content


async def test_edit_single_and_errors(tmp_path):
	ctx = _ctx(tmp_path)
	(tmp_path / "f.txt").write_text("alpha beta alpha")
	dup = await edit(path="f.txt", edits=[{"old": "alpha", "new": "x"}], ctx=ctx)
	assert "not unique (2 matches)" in dup.content
	assert (await edit(path="f.txt", edits=[{"old": "zzz", "new": "x"}], ctx=ctx)).is_error
	res = await edit(path="f.txt", edits=[{"old": "beta", "new": "B"}], ctx=ctx)
	assert "edited f.txt" in res.content
	assert res.details["diff"].startswith("---")  # unified diff emitted
	assert (tmp_path / "f.txt").read_text() == "alpha B alpha"


async def test_edit_multiple_blocks(tmp_path):
	p = tmp_path / "m.txt"
	p.write_text("aaa\nbbb\nccc")
	res = await edit(
		path="m.txt",
		edits=[{"old": "aaa", "new": "A"}, {"old": "ccc", "new": "C"}],
		ctx=_ctx(tmp_path),
	)
	assert "2 block(s)" in res.content
	assert p.read_text() == "A\nbbb\nC"


async def test_edit_overlapping_blocks_rejected(tmp_path):
	p = tmp_path / "o.txt"
	p.write_text("hello world")
	res = await edit(
		path="o.txt",
		edits=[{"old": "hello world", "new": "x"}, {"old": "world", "new": "y"}],
		ctx=_ctx(tmp_path),
	)
	assert res.is_error
	assert "overlap" in res.content
	assert p.read_text() == "hello world"  # atomic: unchanged when any edit fails


async def test_edit_preserves_crlf(tmp_path):
	p = tmp_path / "w.txt"
	p.write_bytes(b"one\r\ntwo\r\nthree\r\n")
	# model sends LF oldText; it must still match against the CRLF file
	res = await edit(path="w.txt", edits=[{"old": "two\nthree", "new": "TWO\nTHREE"}], ctx=_ctx(tmp_path))
	assert "edited" in res.content
	assert p.read_bytes() == b"one\r\nTWO\r\nTHREE\r\n"


async def test_edit_preserves_bom(tmp_path):
	p = tmp_path / "b.txt"
	p.write_bytes(b"\xef\xbb\xbfhello world")
	res = await edit(path="b.txt", edits=[{"old": "world", "new": "there"}], ctx=_ctx(tmp_path))
	assert "edited" in res.content
	assert p.read_bytes() == b"\xef\xbb\xbfhello there"


async def test_read_offset_and_limit(tmp_path):
	(tmp_path / "n.txt").write_text("l1\nl2\nl3\nl4\nl5")
	ctx = _ctx(tmp_path)
	windowed = await read_file(path="n.txt", offset=2, limit=2, ctx=ctx)
	assert windowed.content.startswith("l2\nl3")
	assert "use offset=4 to continue" in windowed.content
	assert (await read_file(path="n.txt", offset=4, ctx=ctx)).content == "l4\nl5"


async def test_read_offset_beyond_eof(tmp_path):
	(tmp_path / "n.txt").write_text("l1\nl2")
	res = await read_file(path="n.txt", offset=99, ctx=_ctx(tmp_path))
	assert res.is_error
	assert "beyond end of file" in res.content


async def test_bash_runs_and_reports_exit_code(tmp_path):
	res = await bash(command="echo hi", ctx=_ctx(tmp_path))
	assert "hi" in res.content
	assert "[exit code: 0]" in res.content
	assert res.is_error is False
	assert res.details["exit_code"] == 0
	assert res.details["duration_seconds"] >= 0


async def test_bash_nonzero_exit(tmp_path):
	res = await bash(command="exit 3", ctx=_ctx(tmp_path))
	assert res.is_error
	assert res.details["exit_code"] == 3


async def test_bash_timeout_from_ctx(tmp_path):
	res = await bash(command="sleep 5", ctx=_ctx(tmp_path, timeout=0.2))
	assert res.is_error
	assert "timed out after 0.2s" in res.content
	assert res.details["timed_out"] is True


async def test_bash_timeout_arg_overrides_ctx(tmp_path):
	# ctx default is 120s; per-call arg wins
	res = await bash(command="sleep 5", timeout=0.2, ctx=_ctx(tmp_path))
	assert res.is_error
	assert "timed out after 0.2s" in res.content


async def test_bash_rejects_bad_timeout(tmp_path):
	res = await bash(command="echo hi", timeout=0, ctx=_ctx(tmp_path))
	assert res.is_error
	assert "timeout must be > 0" in res.content


async def test_bash_abort(tmp_path):
	ctx = _ctx(tmp_path)
	ctx.abort.set()
	res = await bash(command="sleep 5", ctx=ctx)
	assert res.is_error
	assert "[command aborted]" in res.content
	assert res.details["aborted"] is True


async def test_bash_task_cancellation_kills_child_process_group(tmp_path):
	pid_file = tmp_path / "child.pid"
	command = f"sh -c 'sleep 30 & echo $! > {pid_file}; wait'"
	task = asyncio.ensure_future(bash(command=command, ctx=_ctx(tmp_path)))
	for _ in range(100):
		if pid_file.exists() and pid_file.read_text().strip():
			break
		await asyncio.sleep(0.01)
	assert pid_file.exists()
	child_pid = int(pid_file.read_text().strip())

	task.cancel()
	with pytest.raises(asyncio.CancelledError):
		await task

	for _ in range(100):
		try:
			os.kill(child_pid, 0)
		except ProcessLookupError:
			break
		await asyncio.sleep(0.01)
	else:
		pytest.fail("Bash child process survived cancellation")


async def test_bash_truncation_spills_to_temp_file(tmp_path):
	res = await bash(command="seq 3000", ctx=_ctx(tmp_path))
	assert res.details["truncation"]["truncated"] is True
	assert res.details["truncation"]["total_lines"] >= 3000
	path = res.details["full_output_path"]
	assert path and os.path.isfile(path)
	full = open(path, encoding="utf-8").read()
	assert full.strip().splitlines()[-1] == "3000"  # full output preserved
	assert "3000" in res.content  # tail kept in the model-visible slice
	assert f"full output: {path}" in res.content


async def test_grep_finds_and_misses(tmp_path):
	(tmp_path / "a.txt").write_text("needle here\nother line")
	ctx = _ctx(tmp_path)
	found = await grep(pattern="needle", path=".", ctx=ctx)
	assert "needle" in found.content
	assert found.details["matches"] == 1
	miss = await grep(pattern="zzz-nomatch-zzz", path=".", ctx=ctx)
	assert miss.content == "[no matches]"
	assert miss.details["matches"] == 0


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


def test_tools_are_async():
	assert inspect.iscoroutinefunction(bash.func)
