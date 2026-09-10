# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from frappe.runner import SourceWatch


def make_event(event_type="modified", src_path="/app/frappe/thing.py", **extra):
	return SimpleNamespace(event_type=event_type, src_path=src_path, is_directory=False, **extra)


class TestSourceWatch(unittest.TestCase):
	"""Which file system events reload the dev server."""

	def _reloads(self, *events) -> int:
		watch = SourceWatch(threading.Event())
		with patch.object(threading, "Timer") as timer:
			for event in events:
				watch.dispatch(event)
		return timer.call_count

	def test_a_written_python_file_reloads(self):
		self.assertEqual(self._reloads(make_event()), 1)

	def test_a_read_does_not_reload(self):
		# inotify calls a plain read "opened" and "closed_no_write". An import reads
		# the file it loads, so these must not reload or the server never settles.
		self.assertEqual(self._reloads(make_event("opened"), make_event("closed_no_write")), 0)

	def test_other_files_do_not_reload(self):
		self.assertEqual(self._reloads(make_event(src_path="/app/frappe/thing.js")), 0)

	def test_a_directory_does_not_reload(self):
		event = make_event()
		event.is_directory = True
		self.assertEqual(self._reloads(event), 0)

	def test_a_rename_reloads_on_the_new_name(self):
		# A rename carries both paths, and only the new name holds the code.
		event = make_event("moved", src_path="/app/frappe/thing.txt", dest_path="/app/frappe/thing.py")
		self.assertEqual(self._reloads(event), 1)

	def test_one_change_reloads_once(self):
		# The process re-execs, thus a burst of writes must lead to one signal.
		self.assertEqual(self._reloads(make_event(), make_event(), make_event()), 1)

	def test_a_change_while_draining_does_not_reload(self):
		draining = threading.Event()
		draining.set()
		watch = SourceWatch(draining)
		with patch.object(threading, "Timer") as timer:
			watch.dispatch(make_event())
		self.assertEqual(timer.call_count, 0)
