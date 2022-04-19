# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

"""
File based locking utility
"""

import os
from time import time

from frappe.utils import get_site_path, touch_file


class LockTimeoutError(Exception):
	pass


def create_lock(name):
	"""Creates a file in the /locks folder by the given name"""
	lock_path = get_lock_path(name)
	if not check_lock(lock_path):
		return touch_file(lock_path)
	else:
		return False


def lock_exists(name):
	"""Returns True if lock of the given name exists"""
	return os.path.exists(get_lock_path(name))


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
	name = name.lower()
	locks_dir = "locks"
	lock_path = get_site_path(locks_dir, name + ".lock")
	return lock_path
