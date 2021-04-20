from __future__ import unicode_literals

# imports - standard imports
import json
from collections.abc import MutableMapping, MutableSequence, Sequence

# imports - third-party imports
import requests
from urllib.parse import urlparse

# imports - module imports
import frappe
from frappe.exceptions import DuplicateEntryError
from frappe.model.document import Document

session = frappe.session


def get_user_doc(user = None):
	if isinstance(user, Document):
		return user

	user = user or session.user
	user = frappe.get_doc('User', user)

	return user

def squashify(what):
	if isinstance(what, Sequence) and len(what) == 1:
		return what[0]

	return what

def safe_json_loads(*args):
	results = []

	for arg in args:
		try:
			arg = json.loads(arg)
		except Exception:
			pass

		results.append(arg)

	return squashify(results)

def filter_dict(what, keys, ignore = False):
	copy = dict()

	if keys:
		for k in keys:
			if k not in what and not ignore:
				raise KeyError('{key} not in dict.'.format(key = k))
			else:
				copy.update({
					k: what[k]
				})
	else:
		copy = what.copy()

	return copy

def get_if_empty(a, b):
	if not a:
		a = b
	return a

def listify(arg):
	if not isinstance(arg, list):
		arg = [arg]
	return arg

def dictify(arg):
	if isinstance(arg, MutableSequence):
		for i, a in enumerate(arg):
			arg[i] = dictify(a)
	elif isinstance(arg, MutableMapping):
		arg = frappe._dict(arg)

	return arg

def check_url(what, raise_err = False):
	if not urlparse(what).scheme:
		if raise_err:
			raise ValueError('{what} not a valid URL.')
		else:
			return False

	return True

def create_test_user(module):
	try:
		test_user = frappe.new_doc('User')
		test_user.first_name = '{module}'.format(module = module)
		test_user.email      = 'testuser.{module}@example.com'.format(module = module)
		test_user.save()
	except DuplicateEntryError:
		frappe.log('Test User Chat Profile exists.')

def get_emojis():
	redis  = frappe.cache()
	emojis = redis.hget('frappe_emojis', 'emojis')

	if not emojis:
		resp  = requests.get('http://git.io/frappe-emoji')
		if resp.ok:
			emojis = resp.json()
			redis.hset('frappe_emojis', 'emojis', emojis)

	return dictify(emojis)
