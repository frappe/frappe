import datetime
from collections import defaultdict
from pathlib import Path

import frappe
from frappe import _
from frappe.utils import get_site_path, get_url
from frappe.utils.data import convert_utc_to_system_timezone


def get_time(path: Path):
	return convert_utc_to_system_timezone(
		datetime.datetime.fromtimestamp(path.stat().st_mtime, tz=datetime.UTC)
	).strftime("%a %b %d %H:%M %Y")


def get_encrytion_status(path: Path):
	return "-enc" in path.name


def get_size(path: Path):
	size = path.stat().st_size
	mbase = 1024 * 1024

	if size > mbase:
		return f"{size / mbase:.1f}M"

	return f"{size / 1024:.1f}K"


def get_context(context):
	context.no_cache = True
	backup_limit = frappe.get_system_settings("backup_limit")
	backups_path = Path(get_site_path("private", "backups"))
	backup_files = [
		(
			"/backups/" + x.relative_to(backups_path).as_posix(),
			get_time(x),
			get_encrytion_status(x),
			get_size(x),
		)
		for x in backups_path.iterdir()
		if x.is_file() and x.name.endswith("sql.gz")
	]

	backup_files.sort(key=lambda x: x[1], reverse=True)

	return {"files": backup_files[:backup_limit]}


def cleanup_old_backups(backups: dict[str, list[Path]], limit: int):
	backups_to_delete = len(backups) - limit

	if backups_to_delete > 0:
		backups = dict(
			sorted(backups.items(), key=lambda x: max(y.stat().st_ctime for y in x[1]), reverse=True)
		)

		for b_files in list(backups.values())[-backups_to_delete:]:
			for b_file in b_files:
				b_file.unlink()


def delete_downloadable_backups():
	path = Path(get_site_path("private", "backups"))
	backups = defaultdict(list)

	for x in path.iterdir():
		if not x.is_file():
			continue

		# Based on the naming convention of the backup files defined in frappe.utils.backups
		backup_name = x.name.rsplit("-" + frappe.local.site.replace(".", "_"), maxsplit=1)[0]
		backups[backup_name].append(x)

	backup_limit = frappe.get_system_settings("backup_limit")

	cleanup_old_backups(backups, backup_limit)


@frappe.whitelist()
def schedule_files_backup(user_email: str):
	from frappe.utils.background_jobs import enqueue, get_jobs

	frappe.only_for("System Manager")

	queued_jobs = get_jobs(site=frappe.local.site, queue="long")
	method = "frappe.desk.page.backups.backups.backup_files_and_notify_user"

	if method not in queued_jobs[frappe.local.site]:
		enqueue(
			"frappe.desk.page.backups.backups.backup_files_and_notify_user",
			queue="long",
			user_email=user_email,
		)
		frappe.msgprint(_("Queued for backup. You will receive an email with the download link"))
	else:
		frappe.msgprint(_("Backup job is already queued. You will receive an email with the download link"))


def backup_files_and_notify_user(user_email=None):
	from frappe.utils.backups import backup

	backup_files = backup(with_files=True)
	get_downloadable_links(backup_files)

	subject = _("File backup is ready")
	frappe.sendmail(
		recipients=[user_email],
		subject=subject,
		template="file_backup_notification",
		args=backup_files,
		header=[subject, "green"],
	)


def get_downloadable_links(backup_files):
	for key in ["backup_path_files", "backup_path_private_files"]:
		path = backup_files[key]
		backup_files[key] = get_url("/".join(path.split("/")[-2:]))
