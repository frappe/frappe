import random
import time
from threading import Barrier, Thread

import frappe
from frappe.tests import IntegrationTestCase

# Note: These tests are adapted from official tests: https://github.com/pallets/werkzeug/blob/main/tests/test_local.py
# We use them to check if our overrides of localproxy work fine.
# Reused under BSD 3 clause license: https://github.com/pallets/werkzeug/blob/main/LICENSE.txt


class TestFrappeLocal(IntegrationTestCase):
	def test_fuzz_thread_isolation(self):
		"""Fuzz write->read consistency of frappe.local across concurrent requests.

		Each iteration mimics a real Frappe request: it starts by calling
		``frappe.init(force=True)`` (fresh local, like ``init_request``) and ends
		with ``frappe.destroy()`` (releases the local, like the WSGI closing
		iterator). Every thread is its own "worker" serving requests back to back.

		Whatever a thread writes to ``frappe.local`` during a request it must read
		back unchanged - no other thread's writes (or deletes) may ever bleed in,
		and one request's ``init``/``destroy`` must not disturb another's. Random
		sleeps are sprinkled between every write and read so that threads interleave
		aggressively and any shared mutable state / non-isolated storage surfaces as
		a mismatch quickly. ``frappe.local`` is accessed directly everywhere, exactly
		as user/framework code does.
		"""
		# Capture from the main thread's context; worker threads start with an empty one.
		site = frappe.local.site
		sites_path = frappe.local.sites_path

		THREADS = 16
		ITERATIONS = 1000
		MAX_DELAY = 0.001  # seconds; small enough to keep the test fast, big enough to interleave

		# Release all threads at once to maximise overlap instead of letting early threads finish first.
		start = Barrier(THREADS)

		def worker(token: int):
			rng = random.Random(token)
			start.wait()

			for _ in range(ITERATIONS):
				# Start of request: fresh, site-scoped local (mirrors init_request).
				frappe.init(site, sites_path=sites_path, force=True)

				# Write a value tagged with this thread's token.
				value = f"{token}:{rng.random()}"
				frappe.local.fuzz_key = value
				time.sleep(rng.uniform(0, MAX_DELAY))

				# Read it back; it must match exactly what we wrote.
				self.assertEqual(frappe.local.fuzz_key, value)
				time.sleep(rng.uniform(0, MAX_DELAY))

				# Delete it, confirm it's gone.
				del frappe.local.fuzz_key
				time.sleep(rng.uniform(0, MAX_DELAY))
				self.assertFalse(hasattr(frappe.local, "fuzz_key"))

				# End of request: release the local (mirrors frappe.destroy()).
				# Very rarely "forget" to destroy, mimicking a leaked request.
				if rng.random() > 0.001:
					frappe.destroy()

		threads = [Thread(target=worker, args=(token,)) for token in range(THREADS)]
		for thread in threads:
			thread.start()
		for thread in threads:
			thread.join()
