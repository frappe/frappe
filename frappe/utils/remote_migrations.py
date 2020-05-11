import getpass
import sys

import requests
from terminaltables import AsciiTable

import frappe
import frappe.utils.backups


def choose(plans_list):
	plans_table = []
	available_plans = []
	selected_plan = None

	print(f"{len(plans_list)} plans available")

	plans_table.append([x for x in plans_list[0].keys()])
	for plan in plans_list:
		row_data = [x for x in plan.values()]
		available_plans.append(row_data[0])
		plans_table.append(row_data)

	print(AsciiTable(plans_table).table)

	while True:
		if selected_plan:
			break
		else:
			input_plan = input("Send plan?: ")
			if input_plan in available_plans:
				return selected_plan
			else:
				print("Invalid selection...try again")


def filter_apps(app_groups):
	from frappe.utils import get_installed_apps_info

	allowed_apps = []
	filtered_apps = []
	existing_apps = []

	for group in app_groups:
		for app in group.get("apps"):
			app_name = group.get('scrubbed')
			branch = group.get('branch')
			allowed_apps.append(tuple(app_name, branch))

	for app in get_installed_apps_info():
		app_name = app.get('app_name')
		branch = app.get('branch')
		existing_apps.append(tuple(app_name, branch))

	filtered_apps = [app[0] for app in existing_apps if app in allowed_apps]

	return "Vanilla Version 12", filtered_apps


def migrate_to(local_site, remote_site):
	if remote_site in ("frappe.cloud", "frappecloud.com"):
		remote_site = "cloud:8002"
		# remote_site = "frappecloud.com"
		return frappecloud_migrator(local_site, remote_site)
	else:
		print(f"{remote_site} is not supported yet")
		sys.exit(1)


def frappecloud_migrator(local_site, remote_site):
	# test:
	login_url = f"http://{remote_site}/api/method/login"
	upload_url = f"http://{remote_site}/api/method/press.api.site.new"
	files_url = f"http://{remote_site}/api/method/upload_file"
	options_url = f"http://{remote_site}/api/method/press.api.site.options_for_new"

	# production:
	# login_url = f"https://{remote_site}/api/method/login"
	# upload_url = f"https://{remote_site}/api/method/press.api.site.new_from_existing_account"
	# options_url = f"https://{remote_site}/api/method/press.api.site.options_for_new"

	print(f"Frappe Cloud credentials @ {remote_site}")

	username = input("Username: ")
	password = getpass.unix_getpass()
	auth_credentials = {"usr": username, "pwd": password}

	# create frapp_cloud session
	session = requests.Session()
	login_sc = session.post(login_url, auth_credentials)

	if login_sc.ok:
		print(f"Authorization Successful!")

		# get options
		session.headers.update({"X-Press-Team": username})
		site_options_sc = session.post(options_url)

		if site_options_sc.ok:
			site_options = site_options_sc.json()["message"]
			app_groups = site_options_sc.json()["groups"]

		else:
			print(f"Request failed with Status Code: {site_options_sc.status_code}")
			sys.exit(1)

		# set preferences from options
		subdomain = input("Enter subdomain: ")
		plan = choose(site_options['plans'])

		frappe.init(site=local_site)
		frappe.connect()

		# apps currently on site....vanilla.
		selected_group, filtered_apps = filter_apps(app_groups)

		# take backup
		print(f"Taking backup for site {local_site}")
		odb = frappe.utils.backups.new_backup(ignore_files=False, force=True)
		files_session = {}

		# upload files
		for file_type, file_path in [("database", odb.backup_path_db), ("public", odb.backup_path_files), ("private", odb.backup_path_private_files)]:
			file_upload_response = session.post(files_url, data={}, files={
				"file": open(file_path, "rb"),
				"is_private": 1,
				"folder": "Home",
				"method": "press.api.site.upload_backup",
				"type": file_type
			})
			if file_upload_response.ok:
				files_session[file_type] = file_upload_response.json()["message"]
			else:
				print(f"Upload failed for: {file_path}")

		files_uploaded = { k, v["file_url"] for k, v in files_session.items() }

		# push to frappe_cloud
		session.post(upload_url, data={
			"site": {
				"apps": filtered_apps,
				"files": files_uploaded,
				"group": selected_group,
				"name": subdomain,
				"plan": plan
			}
		})
		frappe.destroy()

	else:
		print(f"Request failed with Status Code: {login_sc.status_code}")
