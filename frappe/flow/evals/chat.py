# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""`flow-eval run`: each case's ask through Flow's own chat API as its user, on the site's model."""

import hashlib
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import click

import frappe
from frappe.flow.evals.case import Call, Case, Run, as_user, last_line, run_setup
from frappe.flow.lib.session import ERRORS, FlowServerDown

ABORT_WAIT = 30


class Stop(Exception):
	"""Ends a command early; `records` holds what ran, for the table."""


def preflight(model: str | None) -> str:
	"""The model the chats use; refuses when it, the flow server or the web server is missing."""
	import requests

	from frappe.flow.assistant import ASSISTANT_AGENT_NAME
	from frappe.flow.daemon import lifecycle

	model = model or frappe.db.get_value("Flow Agent", ASSISTANT_AGENT_NAME, "model")
	if not model or not frappe.db.get_value("Flow Model", model, "enabled"):
		raise click.ClickException(
			"Flow has no model on this site. Add one in Desk under Flow's settings, with your own "
			"API key or a local model's address, then run again."
		)
	if not lifecycle.healthy():
		raise click.ClickException("The flow server is not running: `bench flow-server start`.")
	try:
		requests.get(lifecycle.callback_url(), timeout=10)
	except requests.RequestException:
		raise click.ClickException("The bench's web server is not running: `bench start`.") from None
	return model


def run_all(cases: list[Case], arms: list[tuple[Path, int | None]], opts: dict, snapshot) -> list[dict]:
	"""Each case, run number and arm in that order; an arm is a folder and the skill's `enabled`."""
	for folder, _ in arms:
		folder.mkdir(parents=True, exist_ok=True)
		for old in [*folder.glob("*.json"), folder / "prompt.txt"]:
			old.unlink(missing_ok=True)
	commits, records, errors_in_a_row, warned = _commits(), [], 0, False
	try:
		for case in cases:
			for n in range(1, opts["runs"] + 1):
				for folder, enabled in arms:
					if (spent := sum(r["usage"].get("cost") or 0 for r in records)) >= opts["max_cost"]:
						raise Stop(f"stopped at ${spent:.2f}, the --max-cost ceiling")
					snapshot.restore()
					if opts["skill"]:
						frappe.db.set_value("Flow Skill", opts["skill"], "enabled", enabled)
						frappe.db.commit()  # nosemgrep: frappe-manual-commit
					record, provider_error = one_run(case, n, folder, opts["model"], opts["timeout"])
					records.append({**record, "commits": commits})
					(folder / f"{case.name}-{n}.json").write_text(
						json.dumps(records[-1], indent=1, default=str)
					)
					errors_in_a_row = errors_in_a_row + 1 if provider_error else 0
					if errors_in_a_row == 2:
						raise Stop(f"two errors in a row: {record['detail']}")
					if not warned and record["usage"].get("input_tokens") and not record["usage"].get("cost"):
						warned = True
						click.echo("this model reports no cost, so --max-cost cannot stop the run")
	except (Stop, KeyboardInterrupt) as exc:
		stop = exc if isinstance(exc, Stop) else Stop("interrupted")
		stop.records = records
		raise stop from None
	return records


def one_run(case: Case, n: int, folder: Path, model: str | None, timeout: int) -> tuple[dict, bool]:
	"""One chat, and whether it ended in an error of the provider or of Flow."""
	from frappe.flow.api import api

	record = {"case": case.name, "n": n, "label": folder.name, "seconds": None}
	record |= {"started": datetime.now(UTC).isoformat(timespec="seconds")}
	record |= {"ask": case.ask, "user": case.user, "model": None, "status": "error", "detail": None}
	record |= {"reply": "", "tool_calls": [], "usage": {}, "prompt_hash": None}
	try:
		value = run_setup(case)
	except Exception as exc:
		return {**record, "detail": last_line(exc)}, False
	start, session = time.monotonic(), None
	try:
		with as_user(case.user):
			record["prompt_hash"] = _prompt_hash()
			title = f"flow-eval {case.name} {n}"
			session = api.create_session(title=title, approval_mode="Auto-approve", model=model)
			flow_run = api.run(session["name"], case.ask)["run"]
			frappe.db.commit()  # the flow server's callbacks are other requests; nosemgrep: frappe-manual-commit
			status, error = _wait(session["name"], flow_run, timeout)
			doc = frappe.get_doc("Flow Session", session["name"])
			if not (path := folder / "prompt.txt").exists():
				path.write_text(doc.system_prompt() or "")
		output, usage = frappe.db.get_value("Flow Run", flow_run, ["output", "usage"])
		run = Run(output or "", _calls(doc.transcript()), json.loads(usage or "{}"), value)
		model = {"name": doc.model, "model_id": frappe.db.get_value("Flow Model", doc.model, "model_id")}
		record |= {"seconds": round(time.monotonic() - start, 1), "model": model, "reply": run.reply}
		record |= {"tool_calls": [vars(c) for c in run.tool_calls], "usage": run.usage}
	except Exception as exc:
		# a refusal, such as a USER without Flow User, is the case's mistake, not the provider's
		refused = isinstance(exc, frappe.ValidationError | frappe.PermissionError)
		return {**record, "detail": last_line(exc)}, not refused or isinstance(exc, FlowServerDown)
	finally:
		if session:
			_end(session["name"])
	if status == "Running" or status == "Denied" or error in (ERRORS["max_turns"], ERRORS["budget"]):
		# a chat that would not stop points at the flow server, so it counts towards the stop
		return {**record, "status": "fail", "detail": error or "the run was denied"}, "did not stop" in (
			error or ""
		)
	if status == "Paused":
		return {**record, "status": "fail", "detail": "the run stopped to ask the user"}, False
	if status == "Failed":
		return {**record, "detail": error}, True
	try:
		with as_user("Administrator"):
			case.check(run)
	except AssertionError as exc:
		return {**record, "status": "fail", "detail": str(exc) or "check failed"}, False
	except Exception as exc:
		return {**record, "detail": last_line(exc)}, False
	return {**record, "status": "pass"}, False


def _wait(session: str, flow_run: str, timeout: int) -> tuple[str, str | None]:
	"""Poll as the chat panel opens a chat: sync, then read the run. "Running" means no answer."""
	deadline = time.monotonic() + timeout
	while (status := _poll(session, flow_run))[0] not in ("Completed", "Denied", "Failed", "Paused"):
		if time.monotonic() > deadline:
			stopped = _abort(session, flow_run)
			return "Running", f"no answer in {timeout} s" + ("" if stopped else " and the chat did not stop")
		time.sleep(1)
	return status


def _poll(session: str, flow_run: str) -> tuple[str, str | None]:
	from frappe.flow.api import api

	frappe.db.rollback()
	api.session(session)
	frappe.db.commit()  # the sync's writes, before the next read view; nosemgrep: frappe-manual-commit
	return frappe.db.get_value("Flow Run", flow_run, ["status", "error"])


def _abort(session: str, flow_run: str) -> bool:
	from frappe.flow.api import api

	try:
		api.abort(session)
		for _ in range(ABORT_WAIT):
			if _poll(session, flow_run)[0] != "Running":
				return True
			time.sleep(1)
	except Exception:
		frappe.db.rollback()
	return False


def _end(session: str) -> None:
	"""Stop the chat if it still runs, then delete it and the flow server's copy, as its owner."""
	from frappe.flow.api import api

	try:
		with as_user(frappe.db.get_value("Flow Session", session, "owner")):
			if running := frappe.db.get_value("Flow Run", {"session": session, "status": "Running"}):
				_abort(session, running)
			api.delete_session(session)
			frappe.db.commit()  # nosemgrep: frappe-manual-commit
	except Exception:
		frappe.db.rollback()


def _calls(transcript: list[dict]) -> list[Call]:
	results = {m["tool_call_id"]: m["content"] for m in transcript if m["role"] == "tool"}
	calls = [c for message in transcript for c in message.get("tool_calls") or ()]
	return [
		Call(c["function"]["name"], _args(c["function"]["arguments"]), results.get(c["id"])) for c in calls
	]


def _args(text: str | None) -> dict:
	"""A call's arguments; a model can send ones that are not a JSON object."""
	try:
		args = json.loads(text or "{}")
	except ValueError:
		args = text
	return args if isinstance(args, dict) else {"raw": args}


def _prompt_hash() -> str:
	"""Changes with the Assistant's instructions, the skills offered to this user, or a tool's schema."""
	from frappe.flow.assistant import ASSISTANT_AGENT_NAME

	agent = frappe.get_doc("Flow Agent", ASSISTANT_AGENT_NAME)
	tools = json.dumps(agent.client_tool_config(), sort_keys=True, default=str)
	return hashlib.sha256(f"{agent.instructions}\n{agent.skill_index()}\n{tools}".encode()).hexdigest()[:12]


def _commits() -> dict[str, str]:
	def git(app, *args):
		path = frappe.get_app_source_path(app)
		return subprocess.run(["git", "-C", path, *args], capture_output=True, text=True).stdout.strip()

	return {
		app: (git(app, "rev-parse", "--short", "HEAD") or "?")
		+ ("+dirty" if git(app, "status", "--porcelain", "--untracked-files=no") else "")
		for app in frappe.get_installed_apps()
	}
