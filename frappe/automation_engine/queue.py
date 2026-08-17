# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

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


def queue_status(run_after=None) -> str:
	"""Resting status for a queue row with this run_after."""
	if run_after and get_datetime(run_after) > now_datetime():
		return "Scheduled"
	return "Pending"
