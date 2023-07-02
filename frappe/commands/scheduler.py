import sys

import click

import frappe
from frappe.commands import profile, with_each_site, with_site
from frappe.exceptions import SiteNotSpecifiedError


@click.command("trigger-scheduler-event", help="Trigger a scheduler event")
@click.argument("event")
@profile
@with_each_site(lambda d: sys.exit(d.exit_code), {"exit_code": 0})
def trigger_scheduler_event(site, context, event, exit_code):
	import frappe.utils.scheduler

	frappe.connect()
	try:
		frappe.get_doc("Scheduled Job Type", {"method": event}).execute()
	except frappe.DoesNotExistError:
		click.secho(f"Event {event} does not exist!", fg="red")
		exit_code = 1

	return {"exit_code": exit_code}


@click.command("enable-scheduler")
@profile
@with_each_site()
def enable_scheduler(site, context):
	"Enable scheduler"
	import frappe.utils.scheduler

	frappe.connect()
	frappe.utils.scheduler.enable_scheduler()
	frappe.db.commit()
	print("Enabled for", site)


@click.command("disable-scheduler")
@profile
@with_each_site()
def disable_scheduler(site, context):
	"Disable scheduler"
	import frappe.utils.scheduler

	frappe.connect()
	frappe.utils.scheduler.disable_scheduler()
	frappe.db.commit()
	print("Disabled for", site)


@click.command("scheduler")
@click.argument("state", type=click.Choice(["pause", "resume", "disable", "enable", "status"]))
@click.option(
	"--format", "-f", default="text", type=click.Choice(["json", "text"]), help="Output format"
)
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@profile
@with_site
def scheduler(site, context, state: str, format: str, verbose: bool = False):
	"""Control scheduler state."""
	from frappe.utils.scheduler import is_scheduler_inactive, toggle_scheduler

	output = {
		"text": "Scheduler is {status} for site {site}",
		"json": '{{"status": "{status}", "site": "{site}"}}',
	}
	match state:
		case "status":
			frappe.connect()
			status = "disabled" if is_scheduler_inactive(verbose=verbose) else "enabled"
			return print(output[format].format(status=status, site=site))
		case "pause" | "resume":
			from frappe.installer import update_site_config

			update_site_config("pause_scheduler", state == "pause")
		case "enable" | "disable":
			frappe.connect()
			toggle_scheduler(state == "enable")
			frappe.db.commit()

	print(output[format].format(status=f"{state}d", site=site))


@click.command("set-maintenance-mode")
@click.argument("state", type=click.Choice(["on", "off"]))
@profile
@with_site
def set_maintenance_mode(site, context, state):
	"""Put the site in maintenance mode for upgrades."""
	from frappe.installer import update_site_config

	update_site_config("maintenance_mode", 1 if (state == "on") else 0)


@click.command("doctor")
@profile
@with_each_site()
def doctor(site, context):
	"Get diagnostic info about background workers"
	from frappe.utils.doctor import doctor as _doctor

	_doctor(site=site)


@click.command("show-pending-jobs")
@profile
@with_site
def show_pending_jobs(site, context):
	"Get diagnostic info about background jobs"
	from frappe.utils.doctor import pending_jobs as _pending_jobs

	return _pending_jobs(site=site)


@click.command("purge-jobs")
@click.option("--queue", default=None, help='one of "low", "default", "high')
@click.option(
	"--event",
	default=None,
	help='one of "all", "weekly", "monthly", "hourly", "daily", "weekly_long", "daily_long"',
)
@profile
@with_site
def purge_jobs(site, queue=None, event=None):
	"Purge any pending periodic tasks, if event option is not given, it will purge everything for the site"
	from frappe.utils.doctor import purge_pending_jobs

	count = purge_pending_jobs(event=event, site=site, queue=queue)
	print(f"Purged {count} jobs")


@click.command("schedule")
def start_scheduler():
	"""Start scheduler process which is responsible for enqueueing the scheduled job types."""
	from frappe.utils.scheduler import start_scheduler

	start_scheduler()


@click.command("worker")
@click.option(
	"--queue",
	type=str,
	help="Queue to consume from. Multiple queues can be specified using comma-separated string. If not specified all queues are consumed.",
)
@click.option("--quiet", is_flag=True, default=False, help="Hide Log Outputs")
@click.option("-u", "--rq-username", default=None, help="Redis ACL user")
@click.option("-p", "--rq-password", default=None, help="Redis ACL user password")
@click.option("--burst", is_flag=True, default=False, help="Run Worker in Burst mode.")
@click.option(
	"--strategy",
	required=False,
	type=click.Choice(["round_robin", "random"]),
	help="Dequeuing strategy to use",
)
def start_worker(
	queue, quiet=False, rq_username=None, rq_password=None, burst=False, strategy=None
):
	"""Start a backgrond worker"""
	from frappe.utils.background_jobs import start_worker

	start_worker(
		queue,
		quiet=quiet,
		rq_username=rq_username,
		rq_password=rq_password,
		burst=burst,
		strategy=strategy,
	)


@click.command("worker-pool")
@click.option(
	"--queue",
	type=str,
	help="Queue to consume from. Multiple queues can be specified using comma-separated string. If not specified all queues are consumed.",
)
@click.option("--num-workers", type=int, default=2, help="Number of workers to spawn in pool.")
@click.option("--quiet", is_flag=True, default=False, help="Hide Log Outputs")
@click.option("--burst", is_flag=True, default=False, help="Run Worker in Burst mode.")
def start_worker_pool(queue, quiet=False, num_workers=2, burst=False):
	"""Start a backgrond worker"""
	from frappe.utils.background_jobs import start_worker_pool

	start_worker_pool(
		queue=queue,
		quiet=quiet,
		burst=burst,
		num_workers=num_workers,
	)


@click.command("ready-for-migration")
@profile
@with_site
def ready_for_migration(site, context):
	from frappe.utils.doctor import any_job_pending

	pending_jobs = any_job_pending(site=site)
	if pending_jobs:
		print(f"NOT READY for migration: site {site} has pending background jobs")
		sys.exit(1)

	else:
		print(f"READY for migration: site {site} does not have any background jobs")
		return 0


commands = [
	disable_scheduler,
	doctor,
	enable_scheduler,
	purge_jobs,
	ready_for_migration,
	scheduler,
	set_maintenance_mode,
	show_pending_jobs,
	start_scheduler,
	start_worker,
	start_worker_pool,
	trigger_scheduler_event,
]
