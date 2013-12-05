import os
from time import time
from webnotes.utils import get_site_path

class LockTimeoutError(Exception):
    pass

def create_lock(name):
	lock_path = get_lock_path(name)
	if not check_lock(lock_path):
		return touch_file(lock_path)
	else:
		return False

def touch_file(path):
	with open(path, 'a'):
		os.utime(path, None)
	return True

def check_lock(path):
	if not os.path.exists(path):
		return False
	if time() - os.path.getmtime(path) > 600:
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
	lock_path = get_site_path(name + '.lock')
	return lock_path
