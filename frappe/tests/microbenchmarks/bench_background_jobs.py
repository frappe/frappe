from functools import lru_cache

import frappe
from frappe.utils.scheduler import enqueue_events_for_site


def bench_scheduling():
	enqueue_events_for_site(get_site_name())


@lru_cache  # This is "cached" because scheduler destroys locals
def get_site_name():
	return frappe.local.site
