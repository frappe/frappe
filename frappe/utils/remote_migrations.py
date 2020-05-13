# imports - standard imports
import functools
import getpass
import json
import re
import sys

# imports - third party imports
import click
import requests
from terminaltables import AsciiTable

# imports - module imports
import frappe
import frappe.utils.backups
from frappe.utils import get_installed_apps_info


def render_table(data):
	print(AsciiTable(data).table)

def padme(me):
	def empty_line(*args, **kwargs):
		result = me(*args, **kwargs)
		print()
		return result
	return empty_line

@functools.lru_cache(maxsize=1024)
def get_first_party_apps():
	apps = []
	for org in ["frappe", "erpnext"]:
		req = requests.get(f"https://api.github.com/users/{org}/repos", {"type": "sources", "per_page": 200})
		if req.ok:
			apps.extend([x["name"] for x in req.json()])
	return apps


@padme
def choose_plan(plans_list):
	plans_table = []
	available_plans = []

	print(f"{len(plans_list)} plans available")

	plans_table.append([x for x in plans_list[0].keys()])
	for plan in plans_list:
		row_data = [x for x in plan.values()]
		available_plans.append(row_data[0])
		plans_table.append(row_data)

	render_table(plans_table)

	while True:
		input_plan = input("Send plan?: ").strip()
		if input_plan in available_plans:
			print(f"{input_plan} Plan selected ✅")
			return input_plan
		else:
			print("Invalid selection...try again ❌")


def check_app_compat(available_group):
	frappe_upgrade_msg = ""
	trimmed_available_group = set([(app['scrubbed'], app['branch']) for app in available_group['apps']])
	existing_group = set([(app['app_name'], app['branch']) for app in get_installed_apps_info()])

	print("Checking availability of existing app group")
	incompatible_apps = []
	filtered_apps = []
	branch_msgs = []

	for (app, branch) in existing_group:
		if (app, branch) not in trimmed_available_group:
			app_title = [group["name"] for group in available_group["apps"] if group["scrubbed"] == app]
			if app_title:
				app_title = app_title[0]
			is_compat = False
			if app not in get_first_party_apps():
				incompatible_apps.append(app)
				print(f"❌ App {app}:{branch}")
			else:
				available_branch = [a['branch'] for a in available_group['apps'] if a['scrubbed'] == app]
				if not available_branch:
					print(f"App {app} doesn't exist in selected group")
					continue
				else:
					available_branch = available_branch[0]
				print(f"⚠️  {app}:{branch} => {available_branch}")
				branch_msgs.append([app.title(), branch, available_branch])
				filtered_apps.append(app_title)
		else:
			filtered_apps.append(app_title)

	start_msg = "\nSelecting this group will "
	incompatible_apps = f"drop {len(incompatible_apps)} apps: " + ", ".join(incompatible_apps) + " and " if incompatible_apps else ""
	branch_change = "upgrade:\n" + "\n".join(["{}: {} => {}".format(*x) for x in branch_msgs]) if branch_msgs else ""
	changes = (incompatible_apps + branch_change) or "be perfect for you :)"
	warning_message = start_msg + changes

	print(warning_message)

	return is_compat, filtered_apps


def generate_app_group_table(app_groups):
	app_groups_table = [["#", "App Group", "Apps"]]

	for _, app_group in enumerate(app_groups):
		row = [_ + 1, app_group["name"], ", ".join([f"{app['scrubbed']}:{app['branch']}" for app in app_group['apps']])]
		app_groups_table.append(row)

	render_table(app_groups_table)


@padme
def filter_apps(app_groups):
	# try for default group first...then let em select which group
	default_group = [g for g in app_groups if g['default']][0]
	is_compat, filtered_apps = check_app_compat(default_group)

	if not is_compat and not click.confirm("Continue anyway?"):
		generate_app_group_table(app_groups)

		while True:
			try:
				app_group_index = int(input("Select App Group #: ").strip()) - 1
				selected_group = app_groups[app_group_index]
				is_compat, filtered_apps = check_app_compat(selected_group)
			except:
				print("Invalid Selection")
				sys.exit(1)

			if is_compat or click.confirm("Continue anyway?"):
				break

	return default_group['name'], filtered_apps

@padme
def create_session():
	# take user input from STDIN
	username = input("Username: ").strip()
	password = getpass.unix_getpass()

	auth_credentials = {"usr": username, "pwd": password}

	session = requests.Session()
	login_sc = session.post(login_url, auth_credentials)

	if login_sc.ok:
		print(f"Authorization Successful! ✅")
		session.headers.update({"X-Press-Team": username})
		return session
	else:
		print(f"Authorization Failed with Error Code {login_sc.status_code}")


def get_new_site_options():
	site_options_sc = session.post(options_url)

	if site_options_sc.ok:
		site_options = site_options_sc.json()["message"]
		return site_options
	else:
		print(f"Couldn't retrive New site information: {site_options_sc.status_code}")


def is_valid_subdomain(subdomain):
	matched = re.match("^[a-z0-9][a-z0-9-]*[a-z0-9]$", subdomain)
	if matched:
		return True
	print('Subdomain contains invalid characters. Use lowercase characters, numbers and hyphens')


def is_subdomain_available(subdomain):
	res = session.post(site_exists_url, {"subdomain": subdomain})
	if res.ok:
		available = not res.json()['message']
		if not available:
			print('Subdomain already exists! Try another one')

		return available


@padme
def get_subdomain(domain):
	while True:
		subdomain = input("Enter subdomain: ").strip()
		if is_valid_subdomain(subdomain):
			if is_subdomain_available(subdomain):
				print(f"Site Domain: {subdomain}.{domain}")
				return subdomain


@padme
def upload_backup(local_site):
	# take backup
	print(f"Taking backup for site {local_site}")
	odb = frappe.utils.backups.new_backup(ignore_files=False, force=True)
	files_session = {}

	# upload files
	for file_type, file_path in [
				("database", odb.backup_path_db),
				("public", odb.backup_path_files),
				("private", odb.backup_path_private_files)
			]:
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

	files_uploaded = { k: v["file_url"] for k, v in files_session.items() }

	return files_uploaded


def frappecloud_migrator(local_site, remote_site):
	# test (change to https !!!):
	global login_url, upload_url, files_url, options_url, site_exists_url, session

	login_url = f"http://{remote_site}/api/method/login"
	upload_url = f"http://{remote_site}/api/method/press.api.site.new"
	files_url = f"http://{remote_site}/api/method/upload_file"
	options_url = f"http://{remote_site}/api/method/press.api.site.options_for_new"
	site_exists_url = f"http://{remote_site}/api/method/press.api.site.exists"

	print(f"Frappe Cloud credentials @ {remote_site}")

	# get credentials + auth user + start session
	session = create_session()

	if session:
		# connect to site db
		frappe.init(site=local_site)
		frappe.connect()

		# get new site options
		site_options = get_new_site_options()

		# set preferences from site options
		subdomain = get_subdomain(site_options['domain'])
		plan = choose_plan(site_options['plans'])

		app_groups = site_options["groups"]
		selected_group, filtered_apps = filter_apps(app_groups)
		files_uploaded = upload_backup(local_site)

		# push to frappe_cloud
		payload = json.dumps({
			"site": {
				"apps": filtered_apps,
				"files": files_uploaded,
				"group": selected_group,
				"name": subdomain,
				"plan": plan
			}
		})

		session.headers.update({"Content-Type": "application/json; charset=utf-8"})
		site_creation_request = session.post(upload_url, payload)
		frappe.destroy()

		if site_creation_request.ok:
			print(f"Site creation started at {site_creation_request.json()['message']}")
		else:
			print(f"Request failed with error code {site_creation_request.status_code}")


def migrate_to(local_site, remote_site):
	if remote_site in ("frappe.cloud", "frappecloud.com"):
		remote_site = "cloud:8002"
		# remote_site = "frappecloud.com"
		return frappecloud_migrator(local_site, remote_site)
	else:
		print(f"{remote_site} is not supported yet")
		sys.exit(1)
