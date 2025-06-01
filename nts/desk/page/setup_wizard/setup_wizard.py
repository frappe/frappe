# Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json

import nts
from nts import _
from nts.geo.country_info import get_country_info
from nts.permissions import AUTOMATIC_ROLES
from nts.translate import send_translations, set_default_language
from nts.utils import cint, now, strip
from nts.utils.password import update_password

from . import install_fixtures


def get_setup_stages(args):  # nosemgrep
	# App setup stage functions should not include nts.db.commit
	# That is done by nts after successful completion of all stages
	stages = [
		{
			"status": _("Updating global settings"),
			"fail_msg": _("Failed to update global settings"),
			"tasks": [
				{"fn": update_global_settings, "args": args, "fail_msg": "Failed to update global settings"}
			],
		}
	]

	stages += get_stages_hooks(args) + get_setup_complete_hooks(args)

	stages.append(
		{
			# post executing hooks
			"status": _("Wrapping up"),
			"fail_msg": _("Failed to complete setup"),
			"tasks": [{"fn": run_post_setup_complete, "args": args, "fail_msg": "Failed to complete setup"}],
		}
	)

	return stages


@nts.whitelist()
def setup_complete(args):
	"""Calls hooks for `setup_wizard_complete`, sets home page as `desktop`
	and clears cache. If wizard breaks, calls `setup_wizard_exception` hook"""

	# Setup complete: do not throw an exception, let the user continue to desk
	if cint(nts.db.get_single_value("System Settings", "setup_complete")):
		return {"status": "ok"}

	args = parse_args(sanitize_input(args))
	stages = get_setup_stages(args)
	is_background_task = nts.conf.get("trigger_site_setup_in_background")

	if is_background_task:
		process_setup_stages.enqueue(stages=stages, user_input=args, is_background_task=True)
		return {"status": "registered"}
	else:
		return process_setup_stages(stages, args)


@nts.whitelist()
def initialize_system_settings_and_user(system_settings_data, user_data):
	system_settings = nts.get_single("System Settings")

	if cint(system_settings.setup_complete):
		return

	system_settings_data = parse_args(sanitize_input(system_settings_data))
	system_settings.update(
		{
			"language": system_settings_data.get("language"),
			"country": system_settings_data.get("country"),
			"currency": system_settings_data.get("currency"),
			"time_zone": system_settings_data.get("time_zone"),
		}
	)
	system_settings.save()

	user_data = parse_args(sanitize_input(user_data))
	create_or_update_user(user_data)


@nts.task()
def process_setup_stages(stages, user_input, is_background_task=False):
	from nts.utils.telemetry import capture

	capture("initated_server_side", "setup")
	try:
		nts.flags.in_setup_wizard = True
		current_task = None
		for idx, stage in enumerate(stages):
			nts.publish_realtime(
				"setup_task",
				{"progress": [idx, len(stages)], "stage_status": stage.get("status")},
				user=nts.session.user,
			)

			for task in stage.get("tasks"):
				current_task = task
				task.get("fn")(task.get("args"))
	except Exception:
		handle_setup_exception(user_input)
		message = current_task.get("fail_msg") if current_task else "Failed to complete setup"
		nts.log_error(title=f"Setup failed: {message}")
		if not is_background_task:
			nts.response["setup_wizard_failure_message"] = message
			raise
		nts.publish_realtime(
			"setup_task",
			{"status": "fail", "fail_msg": message},
			user=nts.session.user,
		)
	else:
		run_setup_success(user_input)
		capture("completed_server_side", "setup")
		if not is_background_task:
			return {"status": "ok"}
		nts.publish_realtime("setup_task", {"status": "ok"}, user=nts.session.user)
	finally:
		nts.flags.in_setup_wizard = False


def update_global_settings(args):  # nosemgrep
	if args.language and args.language != "English":
		set_default_language(get_language_code(args.lang))
		nts.db.commit()
	nts.clear_cache()

	update_system_settings(args)
	create_or_update_user(args)
	set_timezone(args)


def run_post_setup_complete(args):  # nosemgrep
	disable_future_access()
	nts.db.commit()
	nts.clear_cache()
	# HACK: due to race condition sometimes old doc stays in cache.
	# Remove this when we have reliable cache reset for docs
	nts.get_cached_doc("System Settings") and nts.get_doc("System Settings")


def run_setup_success(args):  # nosemgrep
	for hook in nts.get_hooks("setup_wizard_success"):
		nts.get_attr(hook)(args)
	install_fixtures.install()


def get_stages_hooks(args):  # nosemgrep
	stages = []
	for method in nts.get_hooks("setup_wizard_stages"):
		stages += nts.get_attr(method)(args)
	return stages


def get_setup_complete_hooks(args):  # nosemgrep
	return [
		{
			"status": "Executing method",
			"fail_msg": "Failed to execute method",
			"tasks": [
				{
					"fn": nts.get_attr(method),
					"args": args,
					"fail_msg": "Failed to execute method",
				}
			],
		}
		for method in nts.get_hooks("setup_wizard_complete")
	]


def handle_setup_exception(args):  # nosemgrep
	nts.db.rollback()
	if args:
		traceback = nts.get_traceback(with_context=True)
		print(traceback)
		for hook in nts.get_hooks("setup_wizard_exception"):
			nts.get_attr(hook)(traceback, args)


def update_system_settings(args):  # nosemgrep
	number_format = get_country_info(args.get("country")).get("number_format", "#,###.##")

	# replace these as float number formats, as they have 0 precision
	# and are currency number formats and not for floats
	if number_format == "#.###":
		number_format = "#.###,##"
	elif number_format == "#,###":
		number_format = "#,###.##"

	system_settings = nts.get_doc("System Settings", "System Settings")
	system_settings.update(
		{
			"country": args.get("country"),
			"language": get_language_code(args.get("language")) or "en",
			"time_zone": args.get("timezone"),
			"currency": args.get("currency"),
			"float_precision": 3,
			"rounding_method": "Banker's Rounding",
			"date_format": nts.db.get_value("Country", args.get("country"), "date_format"),
			"time_format": nts.db.get_value("Country", args.get("country"), "time_format"),
			"number_format": number_format,
			"enable_scheduler": 1 if not nts.flags.in_test else 0,
			"backup_limit": 3,  # Default for downloadable backups
			"enable_telemetry": cint(args.get("enable_telemetry")),
		}
	)
	system_settings.save()
	if args.get("enable_telemetry"):
		nts.db.set_default("session_recording_start", now())


def create_or_update_user(args):  # nosemgrep
	email = args.get("email")
	if not email:
		return

	first_name, last_name = args.get("full_name", ""), ""
	if " " in first_name:
		first_name, last_name = first_name.split(" ", 1)

	if user := nts.db.get_value("User", email, ["first_name", "last_name"], as_dict=True):
		if user.first_name != first_name or user.last_name != last_name:
			(
				nts.qb.update("User")
				.set("first_name", first_name)
				.set("last_name", last_name)
				.set("full_name", args.get("full_name"))
			).run()
	else:
		_mute_emails, nts.flags.mute_emails = nts.flags.mute_emails, True

		user = nts.new_doc("User")
		user.update(
			{
				"email": email,
				"first_name": first_name,
				"last_name": last_name,
			}
		)
		user.append_roles(*_get_default_roles())
		user.append_roles("System Manager")
		user.flags.no_welcome_mail = True
		user.insert()

		nts.flags.mute_emails = _mute_emails

	if args.get("password"):
		update_password(email, args.get("password"))


def set_timezone(args):  # nosemgrep
	if args.get("timezone"):
		for name in nts.STANDARD_USERS:
			nts.db.set_value("User", name, "time_zone", args.get("timezone"))


def parse_args(args):  # nosemgrep
	if not args:
		args = nts.local.form_dict
	if isinstance(args, str):
		args = json.loads(args)

	args = nts._dict(args)

	# strip the whitespace
	for key, value in args.items():
		if isinstance(value, str):
			args[key] = strip(value)

	return args


def sanitize_input(args):
	from nts.utils import is_html, strip_html_tags

	if isinstance(args, str):
		args = json.loads(args)

	for key, value in args.items():
		if is_html(value):
			args[key] = strip_html_tags(value)

	return args


def add_all_roles_to(name):
	user = nts.get_doc("User", name)
	user.append_roles(*_get_default_roles())
	user.save()


def _get_default_roles() -> set[str]:
	skip_roles = {
		"Administrator",
		"Customer",
		"Supplier",
		"Partner",
		"Employee",
	}.union(AUTOMATIC_ROLES)
	return set(nts.get_all("Role", pluck="name")) - skip_roles


def disable_future_access():
	nts.db.set_default("desktop:home_page", "workspace")
	# Enable onboarding after install
	nts.db.set_single_value("System Settings", "enable_onboarding", 1)

	nts.db.set_single_value("System Settings", "setup_complete", 1)


@nts.whitelist()
def load_messages(language):
	"""Load translation messages for given language from all `setup_wizard_requires`
	javascript files"""
	from nts.translate import get_messages_for_boot

	nts.clear_cache()
	set_default_language(get_language_code(language))
	nts.db.commit()
	send_translations(get_messages_for_boot())
	return nts.local.lang


@nts.whitelist()
def load_languages():
	language_codes = nts.db.sql(
		"select language_code, language_name from tabLanguage order by name", as_dict=True
	)
	codes_to_names = {}
	for d in language_codes:
		codes_to_names[d.language_code] = d.language_name
	return {
		"default_language": nts.db.get_value("Language", nts.local.lang, "language_name")
		or nts.local.lang,
		"languages": sorted(nts.db.sql_list("select language_name from tabLanguage order by name")),
		"codes_to_names": codes_to_names,
	}


@nts.whitelist()
def load_country():
	from nts.sessions import get_geo_ip_country

	return get_geo_ip_country(nts.local.request_ip) if nts.local.request_ip else None


@nts.whitelist()
def load_user_details():
	return {
		"full_name": nts.cache.hget("full_name", "signup"),
		"email": nts.cache.hget("email", "signup"),
	}


def prettify_args(args):  # nosemgrep
	# remove attachments
	for key, val in args.items():
		if isinstance(val, str) and "data:image" in val:
			filename = val.split("data:image", 1)[0].strip(", ")
			size = round((len(val) * 3 / 4) / 1048576.0, 2)
			args[key] = f"Image Attached: '{filename}' of size {size} MB"

	pretty_args = []
	pretty_args.extend(f"{key} = {args[key]}" for key in sorted(args))
	return pretty_args


def email_setup_wizard_exception(traceback, args):  # nosemgrep
	if not nts.conf.setup_wizard_exception_email:
		return

	pretty_args = prettify_args(args)
	message = """

#### Traceback

<pre>{traceback}</pre>

---

#### Setup Wizard Arguments

<pre>{args}</pre>

---

#### Request Headers

<pre>{headers}</pre>

---

#### Basic Information

- **Site:** {site}
- **User:** {user}""".format(
		site=nts.local.site,
		traceback=traceback,
		args="\n".join(pretty_args),
		user=nts.session.user,
		headers=nts.request.headers if nts.request else "[no request]",
	)

	nts.sendmail(
		recipients=nts.conf.setup_wizard_exception_email,
		sender=nts.session.user,
		subject=f"Setup failed: {nts.local.site}",
		message=message,
		delayed=False,
	)


def log_setup_wizard_exception(traceback, args):  # nosemgrep
	with open("../logs/setup-wizard.log", "w+") as setup_log:
		setup_log.write(traceback)
		setup_log.write(json.dumps(args))


def get_language_code(lang):
	return nts.db.get_value("Language", {"language_name": lang})


def enable_twofactor_all_roles():
	all_role = nts.get_doc("Role", {"role_name": "All"})
	all_role.two_factor_auth = True
	all_role.save(ignore_permissions=True)


def make_records(records, debug=False):
	from nts import _dict
	from nts.modules import scrub

	if debug:
		print("make_records: in DEBUG mode")

	# LOG every success and failure
	for record in records:
		doctype = record.get("doctype")
		condition = record.get("__condition")

		if condition and not condition():
			continue

		doc = nts.new_doc(doctype)
		doc.update(record)

		# ignore mandatory for root
		parent_link_field = "parent_" + scrub(doc.doctype)
		if doc.meta.get_field(parent_link_field) and not doc.get(parent_link_field):
			doc.flags.ignore_mandatory = True

		savepoint = "setup_fixtures_creation"
		try:
			nts.db.savepoint(savepoint)
			doc.insert(ignore_permissions=True, ignore_if_duplicate=True)
		except Exception as e:
			nts.clear_last_message()
			nts.db.rollback(save_point=savepoint)
			exception = record.get("__exception")
			if exception:
				config = _dict(exception)
				if isinstance(e, config.exception):
					config.handler()
				else:
					show_document_insert_error()
			else:
				show_document_insert_error()


def show_document_insert_error():
	print("Document Insert Error")
	print(nts.get_traceback())
	nts.log_error("Exception during Setup")
