# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""A scripted flow server: every turn finishes at once as rows the log recorder reads back."""

from frappe.flow.daemon.client import DaemonError

TITLE = "Daemon title"
PENDING = {
	"id": "c9",
	"name": "delete",
	"args": {"doctype": "ToDo", "names": ["a"]},
	"prompt": "Delete 1 ToDo record\nDelete 1 ToDo: a",
}


def row(seq, kind, **fields):
	return {"seq": seq, "parent_seq": seq - 1, "ts": 0.0, "type": kind, **fields}


def text(value):
	return [{"type": "text", "text": value}]


def call(call_id, name, **arguments):
	return {"type": "tool_call", "id": call_id, "name": name, "arguments": arguments}


def turn(seq, run_id, message="hi"):
	"""A finished turn with one tool call: eight rows from `seq`."""
	return [
		row(seq, "run_started", run_id=run_id),
		row(seq + 1, "user_message", content=message),
		row(seq + 2, "assistant_message", content=[*text("Reading."), call("c1", "read", doctype="ToDo")]),
		row(seq + 3, "usage", input_tokens=10, output_tokens=5, cost=0.5),
		row(seq + 4, "tool_result", tool_call_id="c1", name="read", content="[]"),
		row(seq + 5, "assistant_message", content=text("done")),
		row(seq + 6, "usage", input_tokens=20, output_tokens=2, cache_read_tokens=8, cost=0.25),
		row(seq + 7, "run_ended", reason="done"),
	]


def pause(seq, run_id, message="delete it"):
	"""A turn that stops at a confirmation-gated call: five rows from `seq`."""
	return [
		row(seq, "run_started", run_id=run_id),
		row(seq + 1, "user_message", content=message),
		row(seq + 2, "assistant_message", content=[call("c9", "delete", **PENDING["args"])]),
		row(seq + 3, "approval_required", calls=[PENDING]),
		row(seq + 4, "run_ended", reason="paused"),
	]


def resumed(seq, run_id):
	"""The approved continuation of `pause`: five rows from `seq`."""
	return [
		row(seq, "run_started", run_id=run_id),
		row(seq + 1, "tool_result", tool_call_id="c9", name="delete", content="Deleted 1 ToDo"),
		row(seq + 2, "assistant_message", content=text("Gone.")),
		row(seq + 3, "usage", input_tokens=3, output_tokens=1),
		row(seq + 4, "run_ended", reason="done"),
	]


def compaction(seq, run_id):
	"""A manual compaction, a run of its own that summarizes all before it: four rows from `seq`."""
	return [
		row(seq, "run_started", run_id=run_id),
		row(seq + 1, "compaction", reason="manual", summary="So far: hi.", compact_up_to_seq=seq - 1),
		row(seq + 2, "usage", input_tokens=40, output_tokens=6, cost=0.1),
		row(seq + 3, "run_ended", reason="done"),
	]


def child_pause(seq, run_id, message="look it up"):
	"""A turn whose sub-agent stops at a confirmation-gated call while the turn runs on: nine rows from `seq`."""
	child = {"subagent_id": "c1"}
	return [
		row(seq, "run_started", run_id=run_id),
		row(seq + 1, "user_message", content=message),
		row(
			seq + 2,
			"assistant_message",
			content=[call("c1", "subagent", task="delete it", description="delete it")],
		),
		row(seq + 3, "run_started", run_id=f"{run_id}-c1", **child),
		row(seq + 4, "user_message", content="delete it", **child),
		row(seq + 5, "assistant_message", content=[call("c9", "delete", **PENDING["args"])], **child),
		row(seq + 6, "usage", input_tokens=10, output_tokens=5, cost=0.5, **child),
		row(seq + 7, "approval_required", calls=[PENDING], **child),
		row(seq + 8, "run_ended", reason="paused", **child),
	]


class FakeDaemon:
	def __init__(self, rows=(), *, running=False, title=TITLE, missing=False, broken=None, answer=turn):
		self.rows = list(rows)
		self.running = running
		self.running_for = 0
		self.paused = bool(
			self.rows and self.rows[-1].get("type") == "run_ended" and self.rows[-1].get("reason") == "paused"
		)
		self.title = title
		self.missing = missing
		self.broken = broken
		self.answer = answer
		self.turns = 0
		self.calls = []
		self.configs = {}
		self.waiting = True

	def __enter__(self):
		return self

	def __exit__(self, *exc):
		pass

	def close(self):
		pass

	def next_seq(self):
		return self.rows[-1]["seq"] + 1 if self.rows else 1

	def create_session(self, config):
		self.calls.append(("create_session", config["session_id"]))
		self.configs[config["session_id"]] = config
		return {"session_id": config["session_id"], "config": config}

	def get_session(self, sid):
		self.calls.append(("get_session", sid))
		if self.missing:
			raise DaemonError(404, "session not found")
		if sid == self.broken:
			raise DaemonError(500, "session_log_corrupt")
		running = self.running or self.running_for > 0
		self.running_for = max(0, self.running_for - 1)
		state = "running" if running else "paused" if self.paused else "idle"
		return {
			"session_id": sid,
			"state": state,
			"running": running,
			"latest_seq": self.rows[-1]["seq"] if self.rows else 0,
			"title": self.title,
			"config": self.configs.get(sid, {}),
		}

	def entries(self, sid, *, since=0, path="active"):
		self.calls.append(("entries", sid, since, path))
		return {"entries": [row for row in self.rows if row["seq"] > since]}

	def upload_attachments(self, sid, files):
		self.calls.append(("upload_attachments", sid, [(name, mime) for name, _data, mime in files]))
		return {"attachments": [{"id": f"a{i}", "name": f[0], "kind": "image"} for i, f in enumerate(files)]}

	def cleanup_attachments(self, sid, attachment_ids):
		self.calls.append(("cleanup_attachments", sid, attachment_ids))
		return {"removed": len(attachment_ids)}

	def run(self, sid, message, *, attachments=None):
		call = ("run", sid, message)
		self.calls.append((*call, attachments) if attachments else call)
		if self.paused:
			raise DaemonError(409, "run is paused for approval; resolve it with resume")
		if self.running:
			return {"status": "steered"}
		self.turns += 1
		rows = self.answer(self.next_seq(), f"r{self.turns}", message)
		self.rows += rows
		self.paused = bool(
			rows and rows[-1].get("type") == "run_ended" and rows[-1].get("reason") == "paused"
		)
		return {"status": "started"}

	def resume(self, sid, answers, *, approval_seq):
		self.calls.append(("resume", sid, answers, approval_seq))
		self.paused = False
		self.turns += 1
		self.rows += resumed(self.next_seq(), f"r{self.turns}")
		return {"status": "started"}

	def abort(self, sid):
		self.calls.append(("abort", sid))
		return {"status": "aborting" if self.running else "idle"}

	def cancel_pending(self, sid):
		self.calls.append(("cancel_pending", sid))
		if not self.paused:
			return {"status": "idle"}
		self.paused = False
		return {"status": "cancelled"}

	def rewind(self, sid, target_seq):
		self.calls.append(("rewind", sid, target_seq))
		if self.running:
			raise DaemonError(409, "a run is already active")
		if self.paused:
			raise DaemonError(409, "run is paused for approval; resolve it before rewinding")
		self.rows.append(row(self.next_seq(), "rewind", target_seq=target_seq))
		return {"status": "rewound"}

	def compact(self, sid):
		self.calls.append(("compact", sid))
		if self.running:
			raise DaemonError(409, "a run is already active")
		if self.paused:
			raise DaemonError(409, "run is paused for approval; resolve it before compacting")
		if not self.rows:
			raise DaemonError(409, "nothing to compact")
		self.turns += 1
		self.rows += compaction(self.next_seq(), f"r{self.turns}")
		return {"status": "started"}

	def tool_waiting(self, sid, token):
		self.calls.append(("tool_waiting", sid, token))
		return {"waiting": self.waiting}

	def tool_result(self, sid, token, result):
		self.calls.append(("tool_result", sid, token, result))
		return {"delivered": True}

	def set_model(self, sid, model, **credentials):
		self.calls.append(("set_model", sid, model, credentials))
		return {"model": model}

	def patch_config(self, sid, **fields):
		self.calls.append(("patch_config", sid, fields))
		self.configs.setdefault(sid, {}).update(fields)
		return {"config": self.configs[sid]}

	def delete_session(self, sid):
		self.calls.append(("delete_session", sid))
		if self.missing:
			raise DaemonError(404, "session not found")
		if self.running:
			raise DaemonError(409, "cannot delete a session with an active run")
		self.configs.pop(sid, None)
		return {"status": "deleted"}
