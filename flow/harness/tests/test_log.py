import json
import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from flow_harness.events import AssistantMessage, TextDelta, UserMessage
from flow_harness.session.log import SessionLog, SessionLogError


def test_log_seq_and_replay(tmp_path):
	log = SessionLog(str(tmp_path / "s.jsonl"))
	assert log.append(UserMessage(content="hi")) == 1
	assert log.append(AssistantMessage(content="hello")) == 2
	assert log.latest_seq == 2

	all_rows = log.read_since(0)
	assert [r["seq"] for r in all_rows] == [1, 2]
	assert log.read_since(1)[0]["type"] == "assistant_message"
	assert log.read_since(2) == []


def test_log_survives_reopen(tmp_path):
	path = str(tmp_path / "s.jsonl")
	log = SessionLog(path)
	log.append(UserMessage(content="one"))
	log.append(UserMessage(content="two"))

	reopened = SessionLog(path)  # simulate a daemon restart
	assert reopened.latest_seq == 2
	assert reopened.append(UserMessage(content="three")) == 3


def test_log_rejects_partial_final_line_with_location(tmp_path):
	path = tmp_path / "s.jsonl"
	log = SessionLog(str(path))
	log.append(UserMessage(content="one"))
	with path.open("a") as file:
		file.write('{"type":"user_message"')

	with pytest.raises(SessionLogError, match=r"line 2 is not valid JSON"):
		SessionLog(str(path))


def test_log_rejects_invalid_event_with_location(tmp_path):
	path = tmp_path / "s.jsonl"
	path.write_text(json.dumps({"seq": 1, "type": "unknown"}) + "\n")

	with pytest.raises(SessionLogError, match=r"line 1 is not a valid event"):
		SessionLog(str(path))


def test_log_rejects_pre_release_assistant_shape(tmp_path):
	path = tmp_path / "s.jsonl"
	path.write_text(json.dumps({"seq": 1, "type": "assistant_message", "text": "old shape"}) + "\n")

	with pytest.raises(SessionLogError, match=r"line 1 is not a valid event"):
		SessionLog(str(path))


def test_append_rolls_back_a_partial_write(tmp_path, monkeypatch):
	path = tmp_path / "s.jsonl"
	log = SessionLog(str(path))
	log.append(UserMessage(content="first"))
	healthy = path.read_text()
	real_write, shortened = os.write, []

	def short_once(fd, data):
		if shortened:
			return real_write(fd, data)
		shortened.append(True)
		return real_write(fd, data[: len(data) // 2])  # e.g. the disk filled up

	monkeypatch.setattr(os, "write", short_once)
	with pytest.raises(OSError, match="short write"):
		log.append(UserMessage(content="second"))
	monkeypatch.undo()

	assert path.read_text() == healthy  # the partial line never survives
	log.append(UserMessage(content="third"))  # and the log is still appendable
	assert [row["seq"] for row in SessionLog(str(path)).read_since(0)] == [1, 2]


def test_log_error_locates_the_offending_row(tmp_path):
	path = tmp_path / "s.jsonl"
	log = SessionLog(str(path))
	log.append(UserMessage(content="one"))
	good_line_bytes = path.stat().st_size
	with path.open("a") as file:
		file.write('{"type":"user_message"\n')

	with pytest.raises(SessionLogError) as raised:
		SessionLog(str(path))

	assert raised.value.line == 2
	assert raised.value.offset == good_line_bytes  # byte where the bad row starts
	assert raised.value.reason == "is not valid JSON"


def test_log_rejects_non_monotonic_sequences(tmp_path):
	path = tmp_path / "s.jsonl"
	first = UserMessage(seq=2, content="one").model_dump_json()
	second = UserMessage(seq=1, content="two").model_dump_json()
	path.write_text(f"{first}\n{second}\n")

	with pytest.raises(SessionLogError, match=r"line 2 has non-monotonic seq 1 after 2"):
		SessionLog(str(path))


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


def test_log_does_not_consume_sequence_when_write_fails(tmp_path, monkeypatch):
	log = SessionLog(str(tmp_path / "s.jsonl"))
	real_write = os.write
	failed = False

	def fail_once(fd, data):
		nonlocal failed
		if not failed:
			failed = True
			raise OSError("disk unavailable")
		return real_write(fd, data)

	monkeypatch.setattr(os, "write", fail_once)
	event = UserMessage(content="one")

	with pytest.raises(OSError, match="disk unavailable"):
		log.append(event)

	assert event.seq is None
	assert log.latest_seq == 0
	assert log.append(event) == 1
	assert log.read_since(0)[0]["content"] == "one"


def test_log_rejects_direct_append_of_live_only_event(tmp_path):
	log = SessionLog(str(tmp_path / "s.jsonl"))

	with pytest.raises(ValueError, match="live-only events cannot be appended"):
		log.append(TextDelta(text="transient"))

	assert log.latest_seq == 0


def test_log_file_is_owner_only(tmp_path):
	log = SessionLog(str(tmp_path / "s.jsonl"))
	log.append(UserMessage(content="private"))

	assert oct(os.stat(log.path).st_mode & 0o777) == "0o600"
