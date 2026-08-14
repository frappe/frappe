# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE


import re
import time

import frappe
from frappe.automation_engine import WAITING_STATES

DEFAULT_BATCH_SIZE = 500
DEFAULT_COMMIT_EVERY = 50
QUEUE = "Automation Trigger Queue"
# The RQ queue the drain job runs on; its timeout is what the drain has to finish inside.
DRAIN_QUEUE = "default"
# Share of that timeout a drain will spend claiming, leaving room for the last batch.
DRAIN_TIME_BUDGET = 0.6


def drain(batch_size=DEFAULT_BATCH_SIZE, max_batches=None, executor=None):
	"""Claim and execute due waiting rows until the queue drains or the time budget runs out.

	A drain that outlives its RQ timeout is killed mid-group: the group rolls back, its rows
	sit Running until requeue_stale_running() releases them, and the _rekick() below never
	runs - so the backlog stalls until the next scheduler tick. Stopping short of the timeout
	and letting _rekick() start a fresh job keeps a large backlog moving in clean hops.

	The bound is elapsed time rather than a batch count because no fixed count is safe for
	both: 500 rows is seconds of SetFieldValue work and minutes of HTTP-calling work.
	"""
	from frappe.automation_engine import is_enabled

	if not is_enabled():
		return
	if executor is None:
		from frappe.automation_engine.runner import execute_automation as executor

	promote_due_scheduled()
	deadline = time.monotonic() + drain_time_budget()
	batches = 0
	while True:
		names = claim_batch(batch_size)
		if not names:
			break
		execute_batch(executor, names)
		batches += 1
		if max_batches and batches >= max_batches:
			break
		if time.monotonic() >= deadline:
			break

	if _has_due_pending():
		_rekick()


def drain_time_budget() -> float:
	"""Seconds a drain may keep claiming new batches, from its queue's configured timeout.

	Deliberately a fraction of the timeout, not all of it: the budget is only checked between
	batches, so whichever batch is in flight when it expires still has to finish inside what
	remains. Override with `automation_drain_seconds`.
	"""
	from frappe.utils.background_jobs import get_queues_timeout

	# flt, not cint: a sub-second override is what makes this testable, and cint would floor
	# it to zero and silently hand back the default instead.
	configured = frappe.utils.flt(frappe.conf.get("automation_drain_seconds"))
	if configured > 0:
		return configured
	return (get_queues_timeout().get(DRAIN_QUEUE) or 300) * DRAIN_TIME_BUDGET


def execute_batch(executor, names):
	"""Run a claimed batch in commit groups rather than one transaction per row.

	The runner records step failures itself, but not everything reaches it: a flow deleted
	mid-drain, or a throw while recording the outcome, escapes. Such a row is rolled back to
	its own savepoint, so the rows already run in this group survive it - the guarantee the
	old per-row commit gave, for a fraction of the fsyncs.

	What a savepoint cannot cover is the group commit failing as a whole (deadlock, lock wait
	timeout, a dropped connection). That rolls the group back, and the rows are re-run one at
	a time so a single poisoned row cannot take the rest down with it.
	"""
	for group in _commit_groups(names):
		_execute_group(executor, group)


def _commit_groups(names):
	size = max(1, frappe.utils.cint(frappe.conf.get("automation_commit_every")) or DEFAULT_COMMIT_EVERY)
	for start in range(0, len(names), size):
		yield names[start : start + size]


def _execute_group(executor, names):
	for position, name in enumerate(names):
		_execute_in_savepoint(executor, name, position)
	try:
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title="Automation batch commit failed", message=frappe.get_traceback())
		_execute_serially(executor, names)


def _execute_in_savepoint(executor, name, position):
	savepoint = f"auto_row_{position}"
	frappe.db.savepoint(savepoint)
	try:
		executor(name)
	except Exception:
		frappe.db.rollback(save_point=savepoint)
		frappe.log_error(title=f"Automation run failed: {name}", message=frappe.get_traceback())


def _execute_serially(executor, names):
	"""Re-run a group whose commit failed, one transaction per row.

	The rollback restored every queue row in the group, so the database work is genuinely
	redone rather than duplicated. What the rollback could not reach is the non-transactional
	half of a run that had already finished: its realtime update has been sent, and a failure
	has been counted against the circuit breaker. A retried row can double-count there.
	"""
	for name in names:
		execute_claimed(executor, name)


def execute_claimed(executor, name):
	"""Run one claimed row in a transaction of its own."""
	try:
		executor(name)
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title=f"Automation run failed: {name}", message=frappe.get_traceback())


def promote_due_scheduled():
	"""Move rows whose run_after has arrived from Scheduled to Pending.

	Purely a display concern: claim_batch spans both states, so a row that comes due
	between this and the claim still runs on time.
	"""
	frappe.db.sql(
		f"""
		UPDATE `tab{QUEUE}` SET status = 'Pending'
		WHERE status = 'Scheduled' AND run_after IS NOT NULL AND run_after <= %(now)s
		""",
		{"now": frappe.utils.now()},
	)


def claim_batch(batch_size=DEFAULT_BATCH_SIZE) -> list[str]:
	"""Atomically claim up to `batch_size` due waiting rows and mark them Running."""
	rows = frappe.db.sql(
		f"""
		SELECT name FROM `tab{QUEUE}`
		WHERE status IN %(waiting)s AND (run_after IS NULL OR run_after <= %(now)s)
		ORDER BY triggered_at
		LIMIT %(limit)s
		{_lock_clause()}
		""",
		{
			"now": frappe.utils.now(),
			"limit": frappe.utils.cint(batch_size),
			"waiting": WAITING_STATES,
		},
		as_dict=True,
	)
	if not rows:
		return []

	names = [row.name for row in rows]
	# Stamp modified so a crashed claim can be spotted by requeue_stale_running().
	frappe.db.sql(
		f"UPDATE `tab{QUEUE}` SET status = 'Running', modified = %(now)s WHERE name IN %(names)s",
		{"names": names, "now": frappe.utils.now()},
	)
	frappe.db.commit()
	return names


def _lock_clause() -> str:
	return "FOR UPDATE SKIP LOCKED" if supports_skip_locked() else "FOR UPDATE"


def supports_skip_locked() -> bool:
	"""Whether concurrent claimers can step over each other's locked rows.

	Without it they queue behind one another instead, so running more than one drain shard
	buys lock waits rather than throughput.
	"""
	if frappe.db.db_type != "mariadb":
		return True
	return _mariadb_supports_skip_locked()


def _mariadb_supports_skip_locked() -> bool:
	version = frappe.db.sql("SELECT VERSION()")[0][0]
	return _version_tuple(version) >= (10, 6)


def _version_tuple(version) -> tuple[int, ...]:
	return tuple(int(part) for part in re.findall(r"\d+", version)[:3])


def _has_due_pending() -> bool:
	return bool(
		frappe.db.sql(
			f"""
			SELECT 1 FROM `tab{QUEUE}`
			WHERE status IN %(waiting)s AND (run_after IS NULL OR run_after <= %(now)s)
			LIMIT 1
			""",
			{"now": frappe.utils.now(), "waiting": WAITING_STATES},
		)
	)


def _rekick():
	from frappe.automation_engine.dispatch import kick_drainer

	kick_drainer()


def drain_due():
	"""Scheduler safety net: requeue crashed claims, then drain inline.

	This drains in-process instead of kicking the drain job: the job is deduplicated on a
	fixed id, so a stale Redis job record (a worker killed mid-claim leaves one behind,
	stuck at status "queued" forever) suppresses every later kick. Draining here keeps the
	safety net independent of the thing it is meant to rescue.
	"""
	requeue_stale_running()
	drain()


def requeue_stale_running():
	"""Flip Running rows stuck past the claim timeout back to Pending"""
	minutes = frappe.conf.get("automation_stale_running_minutes") or 30
	cutoff = frappe.utils.add_to_date(frappe.utils.now(), minutes=-minutes)
	frappe.db.sql(
		f"UPDATE `tab{QUEUE}` SET status = 'Pending' WHERE status = 'Running' AND modified < %(cutoff)s",
		{"cutoff": cutoff},
	)


def purge_queue():
	"""Sweep terminal-but-retained rows (Failed/Skipped) older than retention."""
	retention_days = frappe.conf.get("automation_queue_retention_days") or 7
	frappe.db.delete(
		QUEUE,
		{
			"status": ("in", ("Failed", "Skipped")),
			"modified": ("<", frappe.utils.add_days(frappe.utils.now(), -retention_days)),
		},
	)
	frappe.db.delete(
		"Automation Event Subscription",
		{
			"status": ("in", ("Matched", "Timed Out", "Cancelled")),
			"modified": ("<", frappe.utils.add_days(frappe.utils.now(), -retention_days)),
		},
	)
