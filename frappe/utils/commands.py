import functools
import requests
from terminaltables import AsciiTable


@functools.lru_cache(maxsize=1024)
def get_first_party_apps():
	apps = []
	for org in ["frappe", "erpnext"]:
		req = requests.get(f"https://api.github.com/users/{org}/repos", {"type": "sources", "per_page": 200})
		if req.ok:
			apps.extend([x["name"] for x in req.json()])
	return apps


def render_table(data):
	print(AsciiTable(data).table)


def padme(me):
	def empty_line(*args, **kwargs):
		result = me(*args, **kwargs)
		print()
		return result
	return empty_line


def log(message, colour=''):
	colours = {
		"nc": '\033[0m',
		"blue": '\033[94m',
		"green": '\033[92m',
		"yellow": '\033[93m',
		"red": '\033[91m',
		"silver": '\033[90m'
	}
	colour = colours.get(colour, "")
	end_line = '\033[0m'
	print(colour + message + end_line)
