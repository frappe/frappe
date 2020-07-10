import click
import requests
from six import PY3
from html2text import html2text
import frappe


def frappecloud_migrator(local_site):
	print("Retreiving Migrator...")
	remote_site = frappe.conf.frappecloud_url or "frappecloud.com"
	request_url = "https://{}/api/method/press.api.script".format(remote_site)
	request = requests.get(request_url)

	if request.status_code / 100 != 2:
		print("Request exitted with Status Code: {}\nPayload: {}".format(request.status_code, html2text(request.text)))
		click.secho("Some errors occured while recovering the migration script. Please contact us @ Frappe Cloud if this issue persists", fg="yellow")
		return

	script_contents = request.json()["message"]

	if PY3:
		exec(script_contents)
	else:
		exec script_contents
