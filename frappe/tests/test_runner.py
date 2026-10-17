# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import os
import subprocess
import sys
import textwrap
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


class TestCloseInheritedFds(unittest.TestCase):
	"""Which descriptors reach the next generation of the runner.

	The call marks the descriptors of the whole process, so it runs in a child.
	"""

	def _run(self, body: str) -> str:
		script = textwrap.dedent(body)
		child = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=60)
		self.assertEqual(child.returncode, 0, child.stderr)
		return child.stdout.strip()

	def test_an_open_file_closes_on_exec(self):
		# macOS kills a process that closes a guarded descriptor, so the call only
		# marks it and the exec closes it.
		output = self._run("""
			import os
			from frappe.runner import close_inherited_fds

			fd = os.open(os.devnull, os.O_RDONLY)
			os.set_inheritable(fd, True)
			close_inherited_fds()
			os.fstat(fd)
			print(os.get_inheritable(fd))
		""")
		self.assertEqual(output, "False")

	def test_the_systemd_socket_survives(self):
		output = self._run("""
			import os
			import socket
			from frappe.runner import close_inherited_fds, systemd_socket_fd

			listener = socket.socket()
			os.dup2(listener.fileno(), 3)
			os.set_inheritable(3, True)  # as systemd passes it
			os.environ.update(LISTEN_PID=str(os.getpid()), LISTEN_FDS="1")
			close_inherited_fds()
			print(systemd_socket_fd(), os.get_inheritable(3))
		""")
		self.assertEqual(output, "3 True")

	def test_a_socket_for_another_process_is_ignored(self):
		output = self._run("""
			import os
			from frappe.runner import systemd_socket_fd

			os.environ.update(LISTEN_PID=str(os.getppid()), LISTEN_FDS="1")
			print(systemd_socket_fd())
		""")
		self.assertEqual(output, "None")

	def test_the_standard_streams_survive(self):
		output = self._run("""
			import os
			from frappe.runner import close_inherited_fds

			close_inherited_fds()
			os.write(1, b"stdout\\n")
			os.fstat(0)
			os.fstat(2)
			print(all(os.get_inheritable(fd) for fd in (0, 1, 2)))
		""")
		self.assertEqual(output, "stdout\nTrue")

	def test_the_count_stays_flat_across_execs(self):
		output = self._run("""
			import os
			import sys
			from frappe.runner import close_inherited_fds

			if not os.path.isdir("/proc/self/fd"):
				print("skip")
				raise SystemExit

			generation = int(os.environ.get("GENERATION", "0"))
			# An open() of python sets close-on-exec. The leak comes from the
			# libraries that do not, so the descriptor here must outlive an exec.
			fd = os.open(os.devnull, os.O_RDONLY)
			os.set_inheritable(fd, True)
			print(len(os.listdir("/proc/self/fd")), flush=True)
			if generation < 2:
				os.environ["GENERATION"] = str(generation + 1)
				close_inherited_fds()
				os.execv(sys.executable, sys.orig_argv)
		""")
		if output == "skip":
			self.skipTest("no /proc on this platform")
		counts = output.splitlines()
		self.assertEqual(len(counts), 3, output)
		self.assertEqual(len(set(counts)), 1, f"the count grew across the execs: {counts}")
