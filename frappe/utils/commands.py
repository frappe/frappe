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
