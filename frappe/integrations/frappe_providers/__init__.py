# imports - standard imports
# imports - module imports

from frappe.integrations.frappe_providers.frappecloud import frappecloud_migrator

# def is_working_press(remote_site_name: str):
# 	try:
# 		print(f"Checking if {remote_site_name} is a working press")
# 		request_url = f"http://{remote_site_name}/api/method/press.api.script"
# 		request = requests.get(request_url)
# 		if request.status_code / 100 != 2:
# 			click.secho(
# 			"Does not seem to be a working press",
# 			fg="red",
# 			)
# 			return False
# 		return True
# 	except:
# 		click.secho(
# 			"Does not seem to be a valid domain",
# 			fg="yellow",
# 		)
# 		return False


def migrate_to(context):
	return frappecloud_migrator(context)
