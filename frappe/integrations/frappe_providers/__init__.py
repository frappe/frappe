# imports - standard imports
import sys
import requests
from frappe.core.utils import html2text
import click

# imports - module imports
from frappe.integrations.frappe_providers.frappecloud import (
	frappecloud_migrator,
	get_remote_script,
)

def is_working_press(remote_site_name: str):
	try:
		print(f"Checking if {remote_site_name} is a working press")
		request_url = f"http://{remote_site_name}/api/method/press.api.script"
		request = requests.get(request_url)
		if request.status_code / 100 != 2:
			click.secho(
			"Does not seem to be a working press",
			fg="red",
			)
			return False
		return True
	except:
		click.secho(
			"Does not seem to be a valid domain",
			fg="yellow",
		)
		return False

def migrate_to(local_site, frappe_provider):
	if is_working_press(remote_site_name=frappe_provider):
		print("Seems to be a working press.")
		return frappecloud_migrator(local_site, remote_site_name=frappe_provider)
	else:
		return