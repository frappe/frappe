# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import frappe
from frappe.utils import get_datetime, now_datetime

QUEUE = "Automation Trigger Queue"

# The RQ queue the drain job is enqueued on. Shared so that the job and the time budget it has
# to finish inside are always read off the same queue: kick_drainer enqueues here, and the
# drainer sizes its budget from this queue's configured timeout.
DRAIN_QUEUE = "default"

# Queue rows that still owe work. A row waiting on a future run_after sits in Scheduled so the list
# view can tell "waiting for its time" apart from "waiting for a worker"; it moves to Pending once
# it comes due. Both are claimable, so the drainer spans the pair.
WAITING_STATES = ("Pending", "Scheduled")

# How long the "this row already reached the outside world" mark outlives the run that set it.
# Long enough to cover a stalled drain, short enough that the key is not kept forever.
EFFECTS_TTL = 24 * 3600


def queue_status(run_after=None) -> str:
	"""Resting status for a queue row with this run_after."""
	if run_after and get_datetime(run_after) > now_datetime():
		return "Scheduled"
	return "Pending"


def effects_key(row_name: str) -> str:
	return f"automation_effects::{row_name}"


def mark_effects_delivered(row_name: str):
	"""Record, where a rollback cannot reach it, that this row has already acted outside the
	database - a webhook sent, a script that called out. The run may still fail afterwards, but
	re-running it from the top would repeat that call, so the mark outlives the transaction."""
	frappe.cache.set_value(effects_key(row_name), 1, expires_in_sec=EFFECTS_TTL)


def effects_delivered(row_name: str) -> bool:
	# Read past the request-local cache: the mark is written by whichever process ran the row.
	return bool(frappe.cache.get_value(effects_key(row_name), use_local_cache=False))


def clear_effects(row_name: str):
	frappe.cache.delete_value(effects_key(row_name))
