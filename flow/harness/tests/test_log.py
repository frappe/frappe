import json
import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from flow_harness.events import AssistantMessage, TextDelta, UserMessage
from flow_harness.session.log import SessionLog, SessionLogError


def test_log_numbers_rows_privately_and_resumes_after_reopen(tmp_path):
	path = str(tmp_path / "s.jsonl")
	log = SessionLog(path)
	assert log.append(UserMessage(content="hi")) == 1
	assert log.append(AssistantMessage(content="hello")) == 2
	assert log.latest_seq == 2
	assert oct(os.stat(log.path).st_mode & 0o777) == "0o600"

	all_rows = log.read_since(0)
	assert [r["seq"] for r in all_rows] == [1, 2]
	assert log.read_since(1)[0]["type"] == "assistant_message"
	assert log.read_since(2) == []

	reopened = SessionLog(path)  # simulate a daemon restart
	assert reopened.latest_seq == 2
	assert reopened.append(UserMessage(content="three")) == 3


def test_log_refuses_a_bad_row_with_its_location(tmp_path):
	good = UserMessage(seq=2, content="one").model_dump_json() + "\n"
	cases = [
		# a partial final line, as a crash mid-write leaves it
		(good + '{"type":"user_message"', 2, len(good), "is not valid JSON"),
		(json.dumps({"seq": 1, "type": "unknown"}) + "\n", 1, 0, "is not a valid event"),
		(
			good + UserMessage(seq=1, content="two").model_dump_json() + "\n",
			2,
			len(good),
			"has non-monotonic seq 1 after 2",
		),
	]
	for text, line, offset, reason in cases:
		path = tmp_path / "s.jsonl"
		path.write_text(text)
		with pytest.raises(SessionLogError, match=f"line {line} {reason}") as raised:
			SessionLog(str(path))
		assert (raised.value.line, raised.value.offset, raised.value.reason) == (line, offset, reason)


def test_a_refused_or_failed_append_leaves_no_trace(tmp_path, monkeypatch):
	path = tmp_path / "s.jsonl"
	log = SessionLog(str(path))
	log.append(UserMessage(content="first"))
	healthy = path.read_text()
	real_write = os.write

	def short_write(fd, data):
		return real_write(fd, data[: len(data) // 2])  # e.g. the disk filled up

	def failed_write(fd, data):
		raise OSError("disk unavailable")

	cases = [
		(None, TextDelta(text="transient"), ValueError, "live-only events cannot be appended"),
		(short_write, UserMessage(content="second"), OSError, "short write"),
		(failed_write, UserMessage(content="second"), OSError, "disk unavailable"),
	]
	for write, event, error, message in cases:
		if write is not None:
			monkeypatch.setattr(os, "write", write)
		with pytest.raises(error, match=message):
			log.append(event)
		monkeypatch.undo()
		assert path.read_text() == healthy, message  # the partial line never survives
		assert (log.latest_seq, event.seq) == (1, None), message

	retried = cases[-1][1]
	assert log.append(retried) == 2  # the failed appends consumed no sequence
	rows = SessionLog(str(path)).read_since(0)
	assert [(row["seq"], row["content"]) for row in rows] == [(1, "first"), (2, "second")]


def test_log_serializes_concurrent_in_process_appends(tmp_path):
	log = SessionLog(str(tmp_path / "s.jsonl"))

	def append(index: int) -> int:
		return log.append(UserMessage(content=str(index)))

	with ThreadPoolExecutor(max_workers=8) as executor:
		assigned = list(executor.map(append, range(100)))

	rows = log.read_since(0)
	assert sorted(assigned) == list(range(1, 101))
	assert [row["seq"] for row in rows] == list(range(1, 101))
	assert {row["content"] for row in rows} == {str(index) for index in range(100)}
