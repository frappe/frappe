# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Public diagnostics API — recorder profiling, concurrency stats and app versions.

Endpoints were consolidated from `frappe.recorder`, `frappe.concurrency_limiter`
and `frappe.utils.change_log`; the old dotted paths keep working via aliases in
the original modules.
"""

import json
from contextlib import suppress
from typing import Any

import frappe
from frappe import _
from frappe.public_api import public
from frappe.recorder import (
	RECORDER_AUTO_DISABLE,
	RECORDER_INTERCEPT_FLAG,
	RECORDER_REQUEST_HASH,
	RECORDER_REQUEST_SPARSE_HASH,
	RecorderConfig,
	administrator_only,
	do_not_record,
	post_process,
)
from frappe.utils.change_log import get_app_branch, get_app_last_commit_ref
from frappe.utils.frappecloud import on_frappecloud

# ---------------------------------------------------------------------------
# Recorder (request/job/query profiling)
# ---------------------------------------------------------------------------


@public(group="Diagnostics")
@frappe.whitelist()
@do_not_record
@administrator_only
def get_recorder_status(*args: Any, **kwargs: Any) -> bool:
	"""Check whether the recorder is currently intercepting requests.

	:return: True if recording is on.
	"""
	return bool(frappe.cache.get_value(RECORDER_INTERCEPT_FLAG))


@public(group="Diagnostics")
@frappe.whitelist()
@do_not_record
@administrator_only
def start_recorder(
	record_jobs: bool = True,
	record_requests: bool = True,
	record_sql: bool = True,
	profile: bool = False,
	capture_stack: bool = True,
	explain: bool = True,
	request_filter: str = "/",
	jobs_filter: str = "",
	*args: Any,
	**kwargs: Any,
) -> None:
	"""Start recording requests, jobs and queries for performance analysis.

	Recording disables itself automatically after a while.

	:param record_jobs: record background jobs
	:param record_requests: record web requests
	:param record_sql: capture SQL queries
	:param profile: run the cProfile profiler on recorded requests
	:param capture_stack: capture the call stack of each query
	:param explain: run EXPLAIN on recorded queries
	:param request_filter: only record request paths matching this prefix
	:param jobs_filter: only record job names matching this prefix
	"""
	RecorderConfig(
		record_requests=int(record_requests),
		record_jobs=int(record_jobs),
		record_sql=int(record_sql),
		profile=int(profile),
		capture_stack=int(capture_stack),
		explain=int(explain),
		request_filter=request_filter,
		jobs_filter=jobs_filter,
	).store()
	frappe.client_cache.set_value(RECORDER_INTERCEPT_FLAG, True)
	frappe.cache.expire_key(RECORDER_INTERCEPT_FLAG, RECORDER_AUTO_DISABLE)


@public(group="Diagnostics")
@frappe.whitelist()
@do_not_record
@administrator_only
def stop_recorder(*args: Any, **kwargs: Any) -> None:
	"""Stop recording and post-process the recorded data."""
	frappe.client_cache.set_value(RECORDER_INTERCEPT_FLAG, False)
	frappe.enqueue(post_process, now=frappe.in_test)


@public(group="Diagnostics")
@frappe.whitelist()
@do_not_record
@administrator_only
def get_recorded_requests(uuid: str | None = None, *args: Any, **kwargs: Any) -> list | dict | None:
	"""Return recorded requests, or one full record by its uuid.

	:param uuid: uuid of a recorded request; all records (sparse) if not passed
	:return: The recorded request(s).
	"""
	if uuid:
		result = frappe.cache.hget(RECORDER_REQUEST_HASH, uuid)
	else:
		result = list(frappe.cache.hgetall(RECORDER_REQUEST_SPARSE_HASH).values())
	return result


@public(group="Diagnostics")
@frappe.whitelist()
@do_not_record
@administrator_only
def export_recorder_data(*args: Any, **kwargs: Any) -> list:
	"""Export all recorded requests with full details.

	:return: The full recorded request data.
	"""
	return list(frappe.cache.hgetall(RECORDER_REQUEST_HASH).values())


@public(group="Diagnostics")
@frappe.whitelist()
@do_not_record
@administrator_only
def delete_recorder_data(*args: Any, **kwargs: Any) -> None:
	"""Delete all recorded requests."""
	frappe.cache.delete_value(RECORDER_REQUEST_SPARSE_HASH)
	frappe.cache.delete_value(RECORDER_REQUEST_HASH)


@public(group="Diagnostics")
@frappe.whitelist()
@do_not_record
@administrator_only
def import_recorder_data(file: str) -> None:
	"""Import previously exported recorder data from an uploaded file.

	The uploaded file is deleted after a successful import.

	:param file: file_url of the uploaded export
	"""
	file_doc = frappe.get_doc("File", {"file_url": file})
	file_content = json.loads(file_doc.get_content())
	for request in file_content:
		frappe.cache.hset(RECORDER_REQUEST_SPARSE_HASH, request["uuid"], request)
		frappe.cache.hset(RECORDER_REQUEST_HASH, request["uuid"], request)
	file_doc.delete(delete_permanently=True)


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------


@public(group="Diagnostics")
@frappe.whitelist()
def get_concurrency_stats() -> dict:
	"""Return the configured and effective concurrency limits of the site.

	:return: Dict with `cached_limit` and `gunicorn_limit`.
	"""
	from frappe.concurrency_limiter import _default_limit, gunicorn_max_concurrency

	frappe.only_for("System Manager")
	cached_limit = _default_limit()
	gunicorn_limit = gunicorn_max_concurrency()
	return {
		"cached_limit": cached_limit,
		"gunicorn_limit": gunicorn_limit,
	}


# ---------------------------------------------------------------------------
# App versions and updates
# ---------------------------------------------------------------------------


@public(group="Diagnostics")
@frappe.whitelist()
def get_versions() -> dict:
	"""Get versions of all installed apps.

	Example:

	        {
	                "frappe": {
	                        "title": "Frappe Framework",
	                        "version": "5.0.0"
	                }
	        }

	:return: Dict mapping each installed app to its title, description, branch and version.
	"""
	versions = {}
	for app in frappe.get_installed_apps(_ensure_on_bench=True):
		app_hooks = frappe.get_hooks(app_name=app)
		app_color = app_hooks.get("app_color")

		# Prefer add_to_apps_screen logo, then app_logo_url — no frappe fallback
		logo = None
		apps_screen = app_hooks.get("add_to_apps_screen")
		if apps_screen and apps_screen[0].get("logo"):
			logo = apps_screen[0]["logo"]
		elif app_hooks.get("app_logo_url"):
			logo = app_hooks["app_logo_url"][0]

		versions[app] = {
			"title": app_hooks.get("app_title")[0],
			"description": app_hooks.get("app_description")[0],
			"branch": get_app_branch(app),
			"color": app_color[0] if app_color else None,
			"logo": logo,
		}

		if versions[app]["branch"] != "master":
			branch_version = app_hooks.get("{}_version".format(versions[app]["branch"]))
			if branch_version:
				versions[app]["branch_version"] = branch_version[0] + f" ({get_app_last_commit_ref(app)})"

		try:
			versions[app]["version"] = frappe.get_attr(app + ".__version__")
		except AttributeError:
			versions[app]["version"] = "0.0.1"

	return versions


@public(group="Diagnostics")
@frappe.whitelist()
def update_last_known_versions() -> None:
	"""Store the currently installed app versions on the session user.

	Used to decide whether to show the "new updates" popup later.
	"""
	with suppress(frappe.QueryDeadlockError):
		frappe.db.set_value(
			"User",
			frappe.session.user,
			"last_known_versions",
			json.dumps(get_versions()),
			update_modified=False,
		)


@public(group="Diagnostics")
@frappe.whitelist()
def show_update_popup() -> None:
	"""Show the "new updates available" popup to eligible users, at most once."""
	if frappe.get_system_settings("disable_system_update_notification"):
		return
	user = frappe.session.user

	update_info = frappe.cache.get_value("changelog-update-info")
	if not update_info:
		return

	updates = json.loads(update_info)

	# Check if user is int the set of users to send update message to
	update_message = ""
	if frappe.cache.sismember("changelog-update-user-set", user):
		for update_type in updates:
			release_links = ""
			for app in updates[update_type]:
				app = frappe._dict(app)
				security_msg = ""
				if app.security_issues:
					security_msg = (
						_("Contains {0} security fixes")
						if app.security_issues > 1
						else _("Contains {0} security fix")
					)
					security_msg = security_msg.format(frappe.bold(app.security_issues))
					security_msg = f"""( <a href='https://github.com/{app.org_name}/{app.app_name}/security/advisories'
						 target='_blank'>{security_msg}</a> )"""
				release_links += f"""
					<b>{app.title}</b>:
						<a href='https://github.com/{app.org_name}/{app.app_name}/releases/tag/v{app.available_version}'
							target="_blank">
							v{app.available_version}
						</a> {security_msg}<br>
					"""
			if release_links:
				message = _("New {} releases for the following apps are available").format(_(update_type))
				update_message += f"<div class='new-version-log'>{message}<div class='new-version-links'>{release_links}</div></div>"

	primary_action = None
	if on_frappecloud():
		primary_action = {
			"label": _("Update from Frappe Cloud"),
			"client_action": "window.open",
			"args": f"https://frappecloud.com/dashboard/sites/{frappe.local.site}",
		}

	if update_message:
		frappe.msgprint(
			update_message,
			title=_("New updates are available"),
			indicator="green",
			primary_action=primary_action,
		)
		frappe.cache.srem("changelog-update-user-set", user)
