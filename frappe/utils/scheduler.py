# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""
Events:
	always
	daily
	monthly
	weekly
"""

# imports - standard imports
import os
import random
import time
from typing import NoReturn

# imports - module imports
import frappe
from frappe.utils import cint, get_datetime, get_sites, now_datetime
from frappe.utils.background_jobs import set_niceness

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def cprint(*args, **kwargs):
    """Prints only if called from STDOUT"""
    try:
        os.get_terminal_size()
        print(*args, **kwargs)
    except Exception:
        pass


def start_scheduler() -> NoReturn:
    """Run enqueue_events_for_all_sites based on scheduler tick.
	Specify scheduler_interval in seconds in common_site_config.json"""

    tick = cint(frappe.get_conf().scheduler_tick_interval) or 60
    set_niceness()

    while True:
        time.sleep(tick)
        enqueue_events_for_all_sites()


def enqueue_events_for_all_sites() -> None:
    """Loop through sites and enqueue events that are not already queued

    Args:
            None

    Returns:
        None
    """

    if os.path.exists(os.path.join(".", ".restarting")):
        # Don't add task to queue if webserver is in restart mode
        return

    with frappe.init_site():
        sites = get_sites()

    # Sites are sorted in alphabetical order, shuffle to randomize priorities
    random.shuffle(sites)

    for site in sites:
        try:
            enqueue_events_for_site(site=site)
        except Exception:
            frappe.logger("scheduler").debug(f"Failed to enqueue events for site: {site}", exc_info=True)


def enqueue_events_for_site(site: str) -> None:
    """Enqueue events for a specific site.

    Args:
        site (str): The site to enqueue events for.

    Returns:
        None
    """
    def log_exc():
        frappe.logger("scheduler").error(f"Exception in Enqueue Events for Site {site}", exc_info=True)

    try:
        frappe.init(site=site)
        frappe.connect()
        if is_scheduler_inactive():
            return

        enqueue_events(site=site)

        frappe.logger("scheduler").debug(f"Queued events for site {site}")
    except Exception as e:
        if frappe.db.is_access_denied(e):
            frappe.logger("scheduler").debug(f"Access denied for site {site}")
        log_exc()

    finally:
        frappe.destroy()


def enqueue_events(site: str) -> list[str] | None:
    """
    Enqueues jobs based on activity.

    This function takes a site as input and enqueues jobs based on activity. It
    retrieves all 'Scheduled Job Type' documents that are not stopped and
    enqueues the jobs if applicable. It returns a list of enqueued job names.

    Args:
        site (str): The site to enqueue jobs for.

    Returns:
        list[str] | None: A list of enqueued job names, or None if no jobs were enqueued.
    """
    if schedule_jobs_based_on_activity():
        enqueued_jobs = []
        for job_type in frappe.get_all("Scheduled Job Type", filters={"stopped": 0}, fields="*"):
            job_type = frappe.get_doc(doctype="Scheduled Job Type", **job_type)
            if job_type.enqueue():
                enqueued_jobs.append(job_type.method)

        return enqueued_jobs


def is_scheduler_inactive(verbose=True) -> bool:
    """
    Checks if the scheduler is inactive.

    This function checks if the scheduler is inactive by evaluating various
    conditions such as maintenance mode and scheduler disable flags.

    Args:
        verbose (bool, optional): Whether to print verbose output. Defaults to True.

    Returns:
        bool: True if the scheduler is inactive, False otherwise.
    """
    if frappe.local.conf.maintenance_mode:
        if verbose:
            cprint(f"{frappe.local.site}: Maintenance mode is ON")
        return True

    if frappe.local.conf.pause_scheduler:
        if verbose:
            cprint(f"{frappe.local.site}: frappe.conf.pause_scheduler is SET")
        return True

    if is_scheduler_disabled(verbose=verbose):
        return True

    return False


def is_scheduler_disabled(verbose=True) -> bool:
    """
    Checks if the scheduler is disabled.

    This function checks if the scheduler is disabled by evaluating various
    conditions such as the disable_scheduler flag and the enable_scheduler
    setting in the System Settings.

    Args:
        verbose (bool, optional): Whether to print verbose output. Defaults to True.

    Returns:
        bool: True if the scheduler is disabled, False otherwise.
    """
    if frappe.conf.disable_scheduler:
        if verbose:
            cprint(f"{frappe.local.site}: frappe.conf.disable_scheduler is SET")
        return True

    scheduler_disabled = not frappe.utils.cint(
    	frappe.db.get_single_value("System Settings", "enable_scheduler")
    )
    if scheduler_disabled:
        if verbose:
            cprint(f"{frappe.local.site}: SystemSettings.enable_scheduler is UNSET")
    return scheduler_disabled


def toggle_scheduler(enable):
    """
    Toggles the scheduler enable/disable flag.

    This function toggles the enable/disable flag of the scheduler in the system settings.

    Args:
        enable: Whether to enable or disable the scheduler.
    """
    frappe.db.set_single_value("System Settings", "enable_scheduler", int(enable))


def enable_scheduler():
    """Enables the scheduler."""
    toggle_scheduler(True)


def disable_scheduler():
    """Disables the scheduler."""
    toggle_scheduler(False)


def schedule_jobs_based_on_activity(check_time=None):
    """Returns True for active sites defined by Activity Log
    Returns True for inactive sites once in 24 hours."""
    if is_dormant(check_time=check_time):
        # ensure last job is one day old
        last_job_timestamp = _get_last_modified_timestamp("Scheduled Job Log")
        if not last_job_timestamp:
            return True
        else:
            if ((check_time or now_datetime()) - last_job_timestamp).total_seconds() >= 86400:
                # one day is passed since jobs are run, so lets do this
                return True
            else:
                # schedulers run in the last 24 hours, do nothing
                return False
    else:
        # site active, lets run the jobs
        return True


def is_dormant(check_time=None):
    """Checks if a site is dormant.
    Returns True if it has been inactive for a specified number of days."""
    last_activity_log_timestamp = _get_last_modified_timestamp("Activity Log")
    since = (frappe.get_system_settings("dormant_days") or 4) * 86400
    if not last_activity_log_timestamp:
        return True
    if ((check_time or now_datetime()) - last_activity_log_timestamp).total_seconds() >= since:
        return True
    return False


def _get_last_modified_timestamp(doctype):
    """Retrieves the last modified timestamp for a given doctype."""
    timestamp = frappe.db.get_value(
    	doctype, filters={}, fieldname="modified", order_by="modified desc"
    )
    if timestamp:
        return get_datetime(timestamp)


@frappe.whitelist()
def activate_scheduler():
    """
    Activate the scheduler by enabling it and updating the site configuration.

    This function imports the update_site_config() function from the
    frappe.installer module.
    It first checks if the maintenance mode is active, and if so, it raises an exception.
    Next, it checks if the scheduler is disabled and enables it if necessary.
    Finally, it checks if the scheduler is paused and resumes it if necessary.
    """
    from frappe.installer import update_site_config

    frappe.only_for("Administrator")

    if frappe.local.conf.maintenance_mode:
        frappe.throw(frappe._("Scheduler can not be re-enabled when maintenance mode is active."))

    if is_scheduler_disabled():
        enable_scheduler()
    if frappe.conf.pause_scheduler:
        update_site_config("pause_scheduler", 0)


@frappe.whitelist()
def get_scheduler_status():
    """
    Get the current status of the scheduler.

    Returns:
        dict: A dictionary with the key 'status' and the value 'inactive' if
        the scheduler is inactive or 'active' if the scheduler is active.
    """
    if is_scheduler_inactive():
        return {"status": "inactive"}
    return {"status": "active"}
