# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

"""Utils for inter-process synchronization using file-locks.

This file implements a "weak" form lock which is not suitable for synchroniztion. This is only used
for document locking for queue_action.
Use `frappe.utils.synchroniztion.filelock` for process synchroniztion.
"""

import os
from pathlib import Path
from time import time

import frappe
from frappe.utils import get_site_path, touch_file

LOCKS_DIR = "locks"


class LockTimeoutError(Exception):
	pass


def create_lock(name):
	"""Creates a file in the /locks folder by the given name.

	Note: This is a "weak lock" and is prone to race conditions. Do not use this lock for small
	sections of code that execute immediately.

	This is primarily use for locking documents for background submission.
	"""
	lock_path = get_lock_path(name)
	if not check_lock(lock_path):
		return touch_file(lock_path)
	else:
		return False


def lock_exists(name):
	"""Return True if lock of the given name exists."""
	return os.path.exists(get_lock_path(name))


def lock_age(name) -> float:
	"""Return time in seconds since lock was created."""
	return time() - Path(get_lock_path(name)).stat().st_mtime


def check_lock(path, timeout=600):
	if not os.path.exists(path):
		return False
	if time() - os.path.getmtime(path) > timeout:
		raise LockTimeoutError(path)
	return True


def delete_lock(name):
	lock_path = get_lock_path(name)
	try:
		os.remove(lock_path)
	except OSError:
		pass
	return True


def get_lock_path(name):
	return get_site_path(LOCKS_DIR, f"{name.lower()}.lock")


def release_document_locks():
	"""Unlocks all documents that were locked by the current context."""
	for doc in frappe.local.locked_documents:
		doc.unlock()
