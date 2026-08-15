# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

from frappe.utils import get_datetime, now_datetime

QUEUE = "Automation Trigger Queue"

# Queue rows that still owe work. A row waiting on a future run_after sits in Scheduled so the list
# view can tell "waiting for its time" apart from "waiting for a worker"; it moves to Pending once
# it comes due. Both are claimable, so the drainer spans the pair.
WAITING_STATES = ("Pending", "Scheduled")


def queue_status(run_after=None) -> str:
	"""Resting status for a queue row with this run_after."""
	if run_after and get_datetime(run_after) > now_datetime():
		return "Scheduled"
	return "Pending"
