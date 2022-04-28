import functools


@functools.lru_cache(maxsize=1024)
def get_first_party_apps():
	"""Get list of all apps under orgs: frappe. erpnext from GitHub"""
	import requests

	apps = []
	for org in ["frappe", "erpnext"]:
		req = requests.get(
			f"https://api.github.com/users/{org}/repos", {"type": "sources", "per_page": 200}
		)
		if req.ok:
			apps.extend([x["name"] for x in req.json()])
	return apps


def render_table(data):
	from terminaltables import AsciiTable

	print(AsciiTable(data).table)


def add_line_after(function):
	"""Adds an extra line to STDOUT after the execution of a function this decorates"""

	def empty_line(*args, **kwargs):
		result = function(*args, **kwargs)
		print()
		return result

	return empty_line


def add_line_before(function):
	"""Adds an extra line to STDOUT before the execution of a function this decorates"""

	def empty_line(*args, **kwargs):
		print()
		result = function(*args, **kwargs)
		return result

	return empty_line


def log(message, colour=""):
	"""Coloured log outputs to STDOUT"""
	colours = {
		"nc": "\033[0m",
		"blue": "\033[94m",
		"green": "\033[92m",
		"yellow": "\033[93m",
		"red": "\033[91m",
		"silver": "\033[90m",
	}
	colour = colours.get(colour, "")
	end_line = "\033[0m"
	print(colour + message + end_line)


def warn(message, category=None):
	from warnings import warn

	warn(message=message, category=category, stacklevel=2)
