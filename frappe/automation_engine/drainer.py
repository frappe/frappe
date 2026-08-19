# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import re
import time

import frappe
from frappe.automation_engine import runner, settings
from frappe.automation_engine.dispatch import kick_drainer
from frappe.automation_engine.queue import DRAIN_QUEUE, QUEUE, WAITING_STATES
from frappe.utils import add_days, add_to_date, cint, now
from frappe.utils.background_jobs import get_queues_timeout

DEFAULT_BATCH_SIZE = 500
# Share of the drain queue's timeout a drain will spend claiming, leaving room for the last batch.
DRAIN_TIME_BUDGET = 0.6


def drain(batch_size=DEFAULT_BATCH_SIZE, max_batches=None, executor=None):
	"""Claim and execute due waiting rows until the queue drains or the time budget runs out.

	Stopping short of the RQ timeout matters: a drain killed mid-group leaves its rows Running
	until requeue_stale_running() releases them, and never hands off to a fresh job.
	"""
	if not settings.is_enabled():
		return
	# Resolved on the module, not imported by name: the tests swap runner.execute_automation out.
	executor = executor or runner.execute_automation

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
		kick_drainer()


def drain_time_budget() -> float:
	"""Seconds a drain may keep claiming new batches, from its queue's configured timeout.

	A fraction of the timeout, not all of it: the budget is only checked between batches, so the
	batch in flight when it expires still has to finish inside what remains.
	"""
	configured = settings.get("drain_seconds")
	if configured > 0:
		return configured
	return (get_queues_timeout().get(DRAIN_QUEUE) or 300) * DRAIN_TIME_BUDGET


def execute_batch(executor, names):
	"""Run a claimed batch in commit groups rather than one transaction per row."""
	size = max(1, cint(settings.get("commit_every")))
	for start in range(0, len(names), size):
		_execute_group(executor, names[start : start + size])


def _execute_group(executor, names):
	"""Run one commit group. Each row gets a savepoint so a failure cannot take the group down.

	A group commit that fails as a whole (deadlock, lock wait, dropped connection) rolls every row
	back, so they are re-run one at a time instead.
	"""
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
		_settle_escaped_row(name)


def _settle_escaped_row(name):
	"""Release a claimed row whose run escaped the runner's own error handling.

	The runner settles its own failures, but not everything reaches it - a flow deleted mid-drain,
	or a throw while recording the outcome. claim_batch has already committed the Running flip by
	then, so the rollback above cannot undo it and the row would sit Running until
	requeue_stale_running() releases it half an hour later.

	Retried a few times because the usual causes are transient, then failed: a row that throws on
	every claim would otherwise be reclaimed by every drain, forever.
	"""
	attempt = cint(frappe.db.get_value(QUEUE, name, "attempt")) + 1
	exhausted = attempt >= cint(settings.get("max_attempts"))
	frappe.db.set_value(
		QUEUE,
		name,
		{"attempt": attempt, "status": "Failed" if exhausted else "Pending"},
		update_modified=False,
	)


def _execute_serially(executor, names):
	"""Re-run a group whose commit failed, one transaction per row.

	The rollback could not reach the non-transactional half of a run that had already finished: its
	realtime update has been sent, and a failure counted against the circuit breaker. A retried row
	can double-count there.
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
		_settle_escaped_row(name)
		frappe.db.commit()


def promote_due_scheduled():
	"""Move rows whose run_after has arrived from Scheduled to Pending.

	Purely a display concern: claim_batch spans both states.
	"""
	queue = frappe.qb.DocType(QUEUE)
	(
		frappe.qb.update(queue)
		.set(queue.status, "Pending")
		.where(queue.status == "Scheduled")
		.where(queue.run_after.notnull())
		.where(queue.run_after <= now())
	).run()


def claim_batch(batch_size=DEFAULT_BATCH_SIZE) -> list[str]:
	"""Atomically claim up to `batch_size` due waiting rows and mark them Running."""
	# Raw SQL: the query builder has no way to express FOR UPDATE SKIP LOCKED.
	# nosemgrep: the only interpolations are a module constant and a fixed lock clause; every
	# value is a bound parameter.
	rows = frappe.db.sql(
		f"""
		SELECT name FROM `tab{QUEUE}`
		WHERE status IN %(waiting)s AND (run_after IS NULL OR run_after <= %(now)s)
		ORDER BY triggered_at
		LIMIT %(limit)s
		{_lock_clause()}
		""",
		{
			"now": now(),
			"limit": cint(batch_size),
			"waiting": WAITING_STATES,
		},
		as_dict=True,
	)
	if not rows:
		return []

	names = [row.name for row in rows]
	queue = frappe.qb.DocType(QUEUE)
	(
		frappe.qb.update(queue)
		.set(queue.status, "Running")
		# Stamp modified so a crashed claim can be spotted by requeue_stale_running().
		.set(queue.modified, now())
		.where(queue.name.isin(names))
	).run()
	# nosemgrep: the claim has to be visible to other drainers immediately, and the row locks
	# taken above must be released before the (slower) execution phase.
	frappe.db.commit()
	return names


def _lock_clause() -> str:
	return "FOR UPDATE SKIP LOCKED" if supports_skip_locked() else "FOR UPDATE"


def supports_skip_locked() -> bool:
	"""Whether concurrent claimers can step over each other's locked rows.

	Without it they queue behind one another, so extra drain shards buy lock waits, not throughput.
	"""
	if frappe.db.db_type != "mariadb":
		return True
	version = frappe.db.sql("SELECT VERSION()")[0][0]
	return tuple(int(part) for part in re.findall(r"\d+", version)[:3]) >= (10, 6)


def _has_due_pending() -> bool:
	queue = frappe.qb.DocType(QUEUE)
	return bool(
		frappe.qb.from_(queue)
		.select(queue.name)
		.where(queue.status.isin(WAITING_STATES))
		.where(queue.run_after.isnull() | (queue.run_after <= now()))
		.limit(1)
		.run()
	)


def drain_due():
	"""Scheduler safety net: requeue crashed claims, then drain inline.

	Drains in-process rather than kicking the drain job, because a stale Redis job record left by a
	worker killed mid-claim suppresses every later kick on that fixed job id.
	"""
	requeue_stale_running()
	drain()


def requeue_stale_running():
	"""Flip Running rows stuck past the claim timeout back to Pending"""
	cutoff = add_to_date(now(), minutes=-cint(settings.get("stale_running_minutes")))
	queue = frappe.qb.DocType(QUEUE)
	(
		frappe.qb.update(queue)
		.set(queue.status, "Pending")
		.where(queue.status == "Running")
		.where(queue.modified < cutoff)
	).run()


def purge_queue():
	"""Sweep terminal-but-retained rows (Failed/Skipped) older than retention."""
	cutoff = add_days(now(), -cint(settings.get("queue_retention_days")))
	frappe.db.delete(QUEUE, {"status": ("in", ("Failed", "Skipped")), "modified": ("<", cutoff)})
	frappe.db.delete(
		"Automation Event Subscription",
		{"status": ("in", ("Matched", "Timed Out", "Cancelled")), "modified": ("<", cutoff)},
	)
