import asyncio
import os

import pytest

from flow_harness.tools.builtins import bash, edit, read, write
from flow_harness.tools.builtins.common import truncate
from flow_harness.tools.tool import ToolContext


def _ctx(tmp_path, **kw) -> ToolContext:
	return ToolContext(cwd=str(tmp_path), **kw)


async def test_write_then_read_back_in_windows(tmp_path):
	ctx = _ctx(tmp_path)
	res = await write(path="sub/n.txt", content="l1\nl2\nl3\nl4\nl5", ctx=ctx)
	assert "wrote sub/n.txt" in res.content
	assert res.details == {"path": str(tmp_path / "sub" / "n.txt"), "chars": 14, "lines": 5}
	assert (tmp_path / "sub" / "n.txt").read_text() == "l1\nl2\nl3\nl4\nl5"
	assert (await read(path="sub/n.txt", ctx=ctx)).content == "l1\nl2\nl3\nl4\nl5"

	windowed = await read(path="sub/n.txt", offset=2, limit=2, ctx=ctx)
	assert windowed.content.startswith("l2\nl3")
	assert "use offset=4 to continue" in windowed.content
	assert (await read(path="sub/n.txt", offset=4, ctx=ctx)).content == "l4\nl5"


async def test_path_tools_stay_inside_allowed_roots(tmp_path):
	allowed = tmp_path / "allowed"
	outside = tmp_path / "outside"
	shared = tmp_path / "shared"
	for folder in (allowed / ".private", allowed / "target", outside, shared):
		folder.mkdir(parents=True)
	(tmp_path / "outside.txt").write_text("secret")
	(outside / "secret.txt").write_text("secret")
	(allowed / ".private" / "secret.txt").write_text("secret")
	(allowed / ".secret").write_text("needle")
	(allowed / "target" / "note.txt").write_text("hello")
	(shared / "context.txt").write_text("shared context")
	(allowed / "escape").symlink_to(outside, target_is_directory=True)
	(allowed / "inner").symlink_to(allowed / "target", target_is_directory=True)
	(allowed / "visible-link").symlink_to(allowed / ".private", target_is_directory=True)
	ctx = _ctx(allowed, allowed_roots=(str(allowed), str(shared)))
	no_hidden = _ctx(allowed, allowed_roots=(str(allowed), str(shared)), ignore_hidden_files=True)

	for case, call in (
		("read ..", read(path="../outside.txt", ctx=ctx)),
		("write ..", write(path="../created.txt", content="nope", ctx=ctx)),
		("edit ..", edit(path="../outside.txt", edits=[{"old": "secret", "new": "changed"}], ctx=ctx)),
		("read through a symlink", read(path="escape/secret.txt", ctx=ctx)),
		("write through a symlink", write(path="escape/new.txt", content="nope", ctx=ctx)),
		("read a hidden folder", read(path=".private/secret.txt", ctx=no_hidden)),
		("read through a symlink to a hidden folder", read(path="visible-link/secret.txt", ctx=no_hidden)),
	):
		try:
			await call
		except PermissionError as error:
			assert "outside the configured allowed roots" in str(error), case
		else:
			pytest.fail(f"{case} was allowed")
	assert (tmp_path / "outside.txt").read_text() == "secret"
	assert not (tmp_path / "created.txt").exists()
	assert not (outside / "new.txt").exists()

	linked = await read(path="inner/note.txt", ctx=ctx)
	assert linked.content == "hello"
	assert linked.details["path"] == str(allowed / "inner" / "note.txt")  # the path as addressed
	assert (await read(path=str(shared / "context.txt"), ctx=ctx)).content == "shared context"  # any root
	assert (await read(path=".secret", ctx=ctx)).content == "needle"  # hidden files are readable by default


async def test_read_reports_what_it_cannot_show(tmp_path):
	(tmp_path / "clip.mp4").write_bytes(b"\x00\x00\x00\x20ftypisom")
	(tmp_path / "n.txt").write_text("l1\nl2")
	for kwargs, error in (
		({"path": "nope.txt"}, "no such file"),
		({"path": "clip.mp4"}, "[clip.mp4 is a binary file; read shows only text and images]"),
		({"path": "n.txt", "offset": 99}, "beyond end of file"),
	):
		res = await read(**kwargs, ctx=_ctx(tmp_path))
		assert res.is_error, kwargs
		assert error in res.content, kwargs


async def test_edit_replaces_exact_blocks_or_nothing(tmp_path):
	ctx = _ctx(tmp_path)
	path = tmp_path / "f.txt"
	for case, before, edits, after, changed in (
		("one block", b"alpha beta alpha", [("beta", "B")], b"alpha B alpha", 1),
		("two blocks", b"aaa\nbbb\nccc", [("aaa", "A"), ("ccc", "C")], b"A\nbbb\nC", 2),
		# the model sends LF; the CRLF file still matches and keeps its endings
		("crlf", b"one\r\ntwo\r\nthree\r\n", [("two\nthree", "TWO\nTHREE")], b"one\r\nTWO\r\nTHREE\r\n", 2),
		("bom", b"\xef\xbb\xbfhello world", [("world", "there")], b"\xef\xbb\xbfhello there", 1),
	):
		path.write_bytes(before)
		res = await edit(path="f.txt", edits=[{"old": old, "new": new} for old, new in edits], ctx=ctx)
		assert f"edited f.txt ({len(edits)} block(s))" in res.content, case
		assert path.read_bytes() == after, case
		assert res.details["diff"].startswith("---"), case
		# a changed line counts once on each side; diff headers don't count
		assert (res.details["lines_added"], res.details["lines_removed"]) == (changed, changed), case

	path.write_text("alpha beta alpha")
	for edits, error in (
		([{"old": "alpha", "new": "x"}], "not unique (2 matches)"),
		([{"old": "zzz", "new": "x"}], "not found"),
		([{"old": "alpha beta", "new": "x"}, {"old": "beta alpha", "new": "y"}], "overlap"),
	):
		res = await edit(path="f.txt", edits=edits, ctx=ctx)
		assert res.is_error and error in res.content, error
	assert path.read_text() == "alpha beta alpha"  # atomic: unchanged when any edit fails


async def test_bash_reports_exit_codes_timeouts_and_aborts(tmp_path):
	# a command needs approval, a read never does
	assert bash.requires_confirmation and not read.requires_confirmation
	plain, short = _ctx(tmp_path), _ctx(tmp_path, timeout=0.2)
	aborted = _ctx(tmp_path)
	aborted.abort.set()
	for case, ctx, kwargs, is_error, text, details in (
		("exit 0", plain, {"command": "echo hi"}, False, "[exit code: 0]", {"exit_code": 0}),
		("exit 3", plain, {"command": "exit 3"}, True, "[exit code: 3]", {"exit_code": 3}),
		("ctx timeout", short, {"command": "sleep 5"}, True, "timed out after 0.2s", {"timed_out": True}),
		# the ctx default is 120s; the call's own timeout wins
		("call timeout", plain, {"command": "sleep 5", "timeout": 0.2}, True, "timed out after 0.2s", {}),
		("bad timeout", plain, {"command": "echo hi", "timeout": 0}, True, "timeout must be > 0", {}),
		("abort", aborted, {"command": "sleep 5"}, True, "[command aborted]", {"aborted": True}),
	):
		res = await bash(**kwargs, ctx=ctx)
		assert res.is_error is is_error, case
		assert text in res.content, case
		assert details.items() <= res.details.items(), case
		assert not res.details or res.details["duration_seconds"] >= 0, case


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
	os.unlink(path)  # the spill outlives the call by design; the test cleans it up
	assert full.strip().splitlines()[-1] == "3000"  # full output preserved
	assert "3000" in res.content  # tail kept in the model-visible slice
	assert f"full output: {path}" in res.content


def test_tail_cut_keeps_the_end_of_a_long_line():
	for text, kept in (
		("a" * 10 + "b" * 60_000, "b" * 51_200),
		# the cut fills its room with the end of the long line before the kept ones
		("a" * 60_000 + "b" * 1_000 + "\n}", "a" * 50_198 + "b" * 1_000 + "\n}"),
		("b" * 60_000 + "\n", "b" * 51_199 + "\n"),  # a trailing newline no longer empties it
	):
		body, _ = truncate(text, keep="tail")
		assert body == kept, len(text)
