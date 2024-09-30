import click
import requests

import frappe
from frappe.core.utils import html2text


def get_remote_script(remote_site):
	print("Retrieving Site Migrator...")
	request_url = f"https://{remote_site}/api/method/press.api.script"
	request = requests.get(request_url)

	if request.status_code / 100 != 2:
		print(f"Request exited with Status Code: {request.status_code}\nPayload: {html2text(request.text)}")
		click.secho(
			"Some errors occurred while recovering the migration script. Please contact us @ Frappe Cloud if this issue persists",
			fg="yellow",
		)
		return

	return request.json()["message"]


def frappecloud_migrator():
	remote_site_name = "frappecloud.com"
	script_contents = get_remote_script(remote_site=remote_site_name)
	import os
	import sys
	import tempfile

	py = sys.executable
	script = tempfile.NamedTemporaryFile(mode="w")
	script.write(script_contents)
	print(f"Site Migrator stored at {script.name}")
	os.execv(py, [py, script.name])
