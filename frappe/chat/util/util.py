# imports - compatibility imports
import six

# imports - standard imports
try:
	from urlparse import urlparse 	  # PY2
except ImportError:
	from urllib.parse import urlparse # PY3
import ast

# imports - module imports
from   frappe.model.document import Document
from   frappe.exceptions import DoesNotExistError
import frappe

session = frappe.session

def get_user_doc(user = None):
	if isinstance(user, Document):
		return user

	user = user or session.user
	user = frappe.get_doc('User', user)
	
	return user

def safe_literal_eval(what):
	if what and isinstance(what, (six.string_types, six.text_type)):
		what = ast.literal_eval(what)
	
	return what

def check_url(what, raise_err = False):
	if not urlparse(what).scheme:
		if raise_err:
			raise ValueError('{what} not a valid URL.')
		else:
			return False
	
	return True

def user_exist(user):
	try:
		user = get_user_doc(user)
		return True
	except DoesNotExistError:
		return False
