# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

"""Drains the outbox: claims due waiting rows in batches and runs them.

Batches are claimed with FOR UPDATE SKIP LOCKED so multiple drainers run in parallel
without double-executing a row. Each claim marks its rows Running and commits, releasing
the locks before the (slower) execution phase.
"""

import re

import frappe
from frappe.automation_engine import WAITING_STATES

DEFAULT_BATCH_SIZE = 500
QUEUE = "Automation Trigger Queue"


def drain(batch_size=DEFAULT_BATCH_SIZE, max_batches=None, executor=None):
	"""Claim and execute due waiting rows until the queue is drained."""
	from frappe.automation_engine import is_enabled

	if not is_enabled():
		return
	if executor is None:
		from frappe.automation_engine.runner import execute_automation as executor

	promote_due_scheduled()
	batches = 0
	while True:
		names = claim_batch(batch_size)
		if not names:
			break
		for name in names:
			executor(name)
		batches += 1
		if max_batches and batches >= max_batches:
			break

	if _has_due_pending():
		_rekick()


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
	if frappe.db.db_type != "mariadb":
		return "FOR UPDATE SKIP LOCKED"
	if _mariadb_supports_skip_locked():
		return "FOR UPDATE SKIP LOCKED"
	return "FOR UPDATE"


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
