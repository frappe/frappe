# imports - standard imports
import six
import ast

# imports - module imports
from   frappe.model.document import Document
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