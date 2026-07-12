# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

"""Drains the outbox: claims due Pending rows in batches and runs them.

Batches are claimed with FOR UPDATE SKIP LOCKED so multiple drainers run in parallel
without double-executing a row. Each claim marks its rows Running and commits, releasing
the locks before the (slower) execution phase.
"""

import frappe

DEFAULT_BATCH_SIZE = 500
QUEUE = "Automation Trigger Queue"


def drain(batch_size=DEFAULT_BATCH_SIZE, max_batches=None, executor=None):
	"""Claim and execute due Pending rows until the queue is drained."""
	if executor is None:
		from frappe.automation_engine.runner import execute_automation as executor

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


def claim_batch(batch_size=DEFAULT_BATCH_SIZE) -> list[str]:
	"""Atomically claim up to `batch_size` due Pending rows and mark them Running."""
	rows = frappe.db.sql(
		f"""
		SELECT name FROM `tab{QUEUE}`
		WHERE status = 'Pending' AND (run_after IS NULL OR run_after <= %(now)s)
		ORDER BY triggered_at
		LIMIT %(limit)s
		FOR UPDATE SKIP LOCKED
		""",
		{"now": frappe.utils.now(), "limit": frappe.utils.cint(batch_size)},
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


def _has_due_pending() -> bool:
	return bool(
		frappe.db.sql(
			f"""
			SELECT 1 FROM `tab{QUEUE}`
			WHERE status = 'Pending' AND (run_after IS NULL OR run_after <= %(now)s)
			LIMIT 1
			""",
			{"now": frappe.utils.now()},
		)
	)


def _rekick():
	from frappe.automation_engine.dispatch import kick_drainer

	kick_drainer()


def drain_due():
	"""Scheduler safety net: requeue crashed claims, then kick the drainer if due rows wait."""
	requeue_stale_running()
	if _has_due_pending():
		_rekick()


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


def purge_runs():
	"""Sweep old Automation Run logs (retention also enforced via Log Settings)."""
	retention_days = frappe.conf.get("automation_run_retention_days") or 90
	frappe.db.delete(
		"Automation Run",
		{"creation": ("<", frappe.utils.add_days(frappe.utils.now(), -retention_days))},
	)
