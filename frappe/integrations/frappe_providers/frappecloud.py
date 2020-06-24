# imports - standard imports
import getpass
import json
import os
import re
import sys

# imports - third party imports
import click
from html2text import html2text
import requests
from tenacity import retry, stop_after_attempt, wait_fixed

# imports - module imports
import frappe
import frappe.utils.backups
from frappe.utils import get_installed_apps_info
from frappe.utils.commands import render_table, add_line_after, add_line_before


# TODO: check upgrade compatibility


def render_actions_table():
	actions_table = [["#", "Action"]]
	actions = []

	for n, action in enumerate(migrator_actions):
		actions_table.append([n+1, action["title"]])
		actions.append(action["fn"])

	render_table(actions_table)
	return actions


def render_site_table(sites_info):
	sites_table = [["#", "Site Name", "Status"]]
	available_sites = []

	for n, site_data in enumerate(sites_info):
		name, status = site_data["name"], site_data["status"]
		if status in ("Active", "Broken"):
			sites_table.append([n + 1, name, status])
			available_sites.append(name)

	render_table(sites_table)
	return available_sites


def render_teams_table(teams):
	teams_table = [["#", "Team"]]

	for n, team in enumerate(teams):
		teams_table.append([n+1, team])

	render_table(teams_table)


def render_plan_table(plans_list):
	plans_table = [["Plan", "CPU Time"]]
	visible_headers = ["name", "cpu_time_per_day"]

	for plan in plans_list:
		plan, cpu_time = [plan[header] for header in visible_headers]
		plans_table.append([plan, "{} hour{}/day".format(cpu_time, "" if cpu_time < 2 else "s")])

	render_table(plans_table)


def render_group_table(app_groups):
	# title row
	app_groups_table = [["#", "App Group", "Apps"]]

	# all rows
	for idx, app_group in enumerate(app_groups):
		apps_list = ", ".join(["{}:{}".format(app["scrubbed"], app["branch"]) for app in app_group["apps"]])
		row = [idx + 1, app_group["name"], apps_list]
		app_groups_table.append(row)

	render_table(app_groups_table)


def handle_request_failure(request=None, message=None, traceback=True, exit_code=1):
	message = message or "Request failed with error code {}".format(request.status_code)
	response = html2text(request.text) if traceback else ""

	print("{0}{1}".format(message, "\n" + response))
	sys.exit(exit_code)


@add_line_after
def select_primary_action():
	actions = render_actions_table()
	idx = click.prompt("What do you want to do?", type=click.IntRange(1, len(actions))) - 1

	return actions[idx]


@add_line_after
def select_site():
	get_all_sites_request = session.post(all_site_url, headers={
		"accept": "application/json",
		"accept-encoding": "gzip, deflate, br",
		"content-type": "application/json; charset=utf-8"
	})

	if get_all_sites_request.ok:
		all_sites = get_all_sites_request.json()["message"]
		available_sites = render_site_table(all_sites)

		while True:
			selected_site = click.prompt("Name of the site you want to restore to", type=str).strip()
			if selected_site in available_sites:
				return selected_site
			else:
				print("Site {} does not exist. Try again ❌".format(selected_site))
	else:
		print("Couldn't retrive sites list...Try again later")
		sys.exit(1)


@add_line_before
def select_team(session):
	# get team options
	account_details_sc = session.post(account_details_url)
	if account_details_sc.ok:
		account_details = account_details_sc.json()["message"]
		available_teams = account_details["teams"]

	# ask if they want to select, go ahead with if only one exists
	if len(available_teams) == 1:
		team = available_teams[0]
	else:
		render_teams_table(available_teams)
		idx = click.prompt("Select Team", type=click.IntRange(1, len(available_teams))) - 1
		team = available_teams[idx]

	print("Team '{}' set for current session".format(team))

	return team


@retry(stop=stop_after_attempt(5))
def get_new_site_options():
	site_options_sc = session.post(options_url)

	if site_options_sc.ok:
		site_options = site_options_sc.json()["message"]
		return site_options
	else:
		print("Couldn't retrive New site information: {}".format(site_options_sc.status_code))


def is_valid_subdomain(subdomain):
	if len(subdomain) < 5:
		print("Subdomain too short. Use 5 or more characters")
		return False
	matched = re.match("^[a-z0-9][a-z0-9-]*[a-z0-9]$", subdomain)
	if matched:
		return True
	print("Subdomain contains invalid characters. Use lowercase characters, numbers and hyphens")


@retry(stop=stop_after_attempt(5))
def is_subdomain_available(subdomain):
	res = session.post(site_exists_url, {"subdomain": subdomain})
	if res.ok:
		available = not res.json()["message"]
		if not available:
			print("Subdomain already exists! Try another one")

		return available


@add_line_after
def choose_plan(plans_list):
	print("{} plans available".format(len(plans_list)))
	available_plans = [plan["name"] for plan in plans_list]
	render_plan_table(plans_list)

	while True:
		input_plan = click.prompt("Select Plan").strip()
		if input_plan in available_plans:
			print("{} Plan selected ✅".format(input_plan))
			return input_plan
		else:
			print("Invalid Selection ❌")


@add_line_after
def check_app_compat(available_group):
	is_compat = True
	incompatible_apps, filtered_apps, branch_msgs = [], [], []
	existing_group = [(app["app_name"], app["branch"]) for app in get_installed_apps_info()]
	print("Checking availability of existing app group")

	for (app, branch) in existing_group:
		info = [ (a["name"], a["branch"]) for a in available_group["apps"] if a["scrubbed"] == app ]
		if info:
			app_title, available_branch = info[0]

			if branch != available_branch:
				print("⚠️  App {}:{} => {}".format(app, branch, available_branch))
				branch_msgs.append([app, branch, available_branch])
				filtered_apps.append(app_title)
				is_compat = False

			else:
				print("✅ App {}:{}".format(app, branch))
				filtered_apps.append(app_title)

		else:
			incompatible_apps.append(app)
			print("❌ App {}:{}".format(app, branch))
			is_compat = False

	start_msg = "\nSelecting this group will "
	incompatible_apps = ("\n\nDrop the following apps:\n" + "\n".join(incompatible_apps)) if incompatible_apps else ""
	branch_change = ("\n\nUpgrade the following apps:\n" + "\n".join(["{}: {} => {}".format(*x) for x in branch_msgs])) if branch_msgs else ""
	changes = (incompatible_apps + branch_change) or "be perfect for you :)"
	warning_message = start_msg + changes
	print(warning_message)

	return is_compat, filtered_apps


@add_line_after
def filter_apps(app_groups):
	render_group_table(app_groups)

	while True:
		app_group_index = click.prompt("Select App Group Number", type=int) - 1
		try:
			if app_group_index == -1:
				raise IndexError
			selected_group = app_groups[app_group_index]
		except IndexError:
			print("Invalid Selection ❌")
			continue

		is_compat, filtered_apps = check_app_compat(selected_group)

		if is_compat or click.confirm("Continue anyway?"):
			print("App Group {} selected! ✅".format(selected_group["name"]))
			break

	return selected_group["name"], filtered_apps


@add_line_after
def get_subdomain(domain):
	while True:
		subdomain = click.prompt("Enter subdomain").strip()
		if is_valid_subdomain(subdomain) and is_subdomain_available(subdomain):
			print("Site Domain: {}.{}".format(subdomain, domain))
			return subdomain


@retry(stop=stop_after_attempt(2), wait=wait_fixed(5))
def upload_backup_file(file_type, file_path):
	return session.post(files_url, data={}, files={
		"file": open(file_path, "rb"),
		"is_private": 1,
		"folder": "Home",
		"method": "press.api.site.upload_backup",
		"type": file_type
	})


@add_line_after
def upload_backup(local_site):
	# take backup
	files_session = {}
	print("Taking backup for site {}".format(local_site))
	odb = frappe.utils.backups.new_backup(ignore_files=False, force=True)

	# upload files
	for x, (file_type, file_path) in enumerate([
				("database", odb.backup_path_db),
				("public", odb.backup_path_files),
				("private", odb.backup_path_private_files)
			]):
		file_name = file_path.split(os.sep)[-1]

		print("Uploading {} file: {} ({}/3)".format(file_type, file_name, x+1))
		file_upload_response = upload_backup_file(file_type, file_path)

		if file_upload_response.ok:
			files_session[file_type] = file_upload_response.json()["message"]
		else:
			print("Upload failed for: {}".format(file_path))

	files_uploaded = { k: v["file_url"] for k, v in files_session.items() }
	print("Uploaded backup files! ✅")

	return files_uploaded


def new_site(local_site):
	# get new site options
	site_options = get_new_site_options()

	# set preferences from site options
	subdomain = get_subdomain(site_options["domain"])
	plan = choose_plan(site_options["plans"])

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

	if site_creation_request.ok:
		site_url = site_creation_request.json()["message"]
		print("Your site {} is being migrated ✨".format(local_site))
		print("View your site dashboard at {}/dashboard/#/sites/{}".format(remote_site, site_url))
		print("Your site URL: {}".format(site_url))
	else:
		handle_request_failure(site_creation_request)


def restore_site(local_site):
	# get list of existing sites they can restore
	selected_site = select_site()

	# TODO: check if they can restore it

	click.confirm("This is an irreversible action. Are you sure you want to continue?", abort=True)

	# backup site
	files_uploaded = upload_backup(local_site)

	# push to frappe_cloud
	payload = json.dumps({
		"name": selected_site,
		"files": files_uploaded
	})
	headers = {"Content-Type": "application/json; charset=utf-8"}
	site_restore_request = session.post(restore_site_url, payload, headers=headers)

	if site_restore_request.ok:
		print("Your site {0} is being restored on {1} ✨".format(local_site, selected_site))
		print("View your site dashboard at {}/dashboard/#/sites/{}".format(remote_site, selected_site))
		print("Your site URL: {}".format(selected_site))
	else:
		handle_request_failure(site_restore_request)


@add_line_after
def create_session():
	print("Frappe Cloud credentials @ {}".format(remote_site))

	# take user input from STDIN
	username = click.prompt("Username").strip()
	password = getpass.unix_getpass()

	auth_credentials = {"usr": username, "pwd": password}

	session = requests.Session()
	login_sc = session.post(login_url, auth_credentials)

	if login_sc.ok:
		print("Authorization Successful! ✅")
		team = select_team(session)
		session.headers.update({
			"X-Press-Team": team,
			"Connection": "keep-alive"
		})
		return session
	else:
		handle_request_failure(message="Authorization Failed with Error Code {}".format(login_sc.status_code), traceback=False)


def frappecloud_migrator(local_site, frappecloud_site):
	global login_url, upload_url, files_url, options_url, site_exists_url, restore_site_url, account_details_url, all_site_url
	global session, migrator_actions, remote_site

	remote_site = frappe.conf.frappecloud_url or "frappecloud.com"

	login_url = "https://{}/api/method/login".format(remote_site)
	upload_url = "https://{}/api/method/press.api.site.new".format(remote_site)
	files_url = "https://{}/api/method/upload_file".format(remote_site)
	options_url = "https://{}/api/method/press.api.site.options_for_new".format(remote_site)
	site_exists_url = "https://{}/api/method/press.api.site.exists".format(remote_site)
	account_details_url = "https://{}/api/method/press.api.account.get".format(remote_site)
	all_site_url = "https://{}/api/method/press.api.site.all".format(remote_site)
	restore_site_url = "https://{}/api/method/press.api.site.restore".format(remote_site)

	migrator_actions = [
		{ "title": "Create a new site", "fn": new_site },
		{ "title": "Restore to an existing site", "fn": restore_site }
	]

	# get credentials + auth user + start session
	session = create_session()

	# available actions defined in migrator_actions
	primary_action = select_primary_action()

	primary_action(local_site)
