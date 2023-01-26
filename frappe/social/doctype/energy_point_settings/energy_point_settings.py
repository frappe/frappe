# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document
from frappe.social.doctype.energy_point_log.energy_point_log import create_review_points_log
from frappe.utils import add_to_date, getdate, today


class EnergyPointSettings(Document):
	pass


def is_energy_point_enabled():
	return frappe.db.get_single_value("Energy Point Settings", "enabled", True)


def allocate_review_points():
	settings = frappe.get_single("Energy Point Settings")

	if not can_allocate_today(
		settings.last_point_allocation_date, settings.point_allocation_periodicity
	):
		return

	user_point_map = {}

	for level in settings.review_levels:
		users = get_users_with_role(level.role)
		for user in users:
			user_point_map.setdefault(user, 0)
			# to avoid duplicate point allocation
			user_point_map[user] = max([user_point_map[user], level.review_points])

	for user, points in user_point_map.items():
		create_review_points_log(user, points)

	settings.last_point_allocation_date = today()
	settings.save(ignore_permissions=True)


def can_allocate_today(last_date, periodicity):
	if not last_date:
		return True

	days_to_add = {"Daily": 1, "Weekly": 7, "Monthly": 30}.get(periodicity, 1)

	next_allocation_date = add_to_date(last_date, days=days_to_add)

	return getdate(next_allocation_date) <= getdate()


def get_users_with_role(role):
	return [
		p[0]
		for p in frappe.db.sql(
			"""SELECT DISTINCT `tabUser`.`name`
		FROM `tabHas Role`, `tabUser`
		WHERE `tabHas Role`.`role`=%s
		AND `tabUser`.`name`!='Administrator'
		AND `tabHas Role`.`parent`=`tabUser`.`name`
		AND `tabUser`.`enabled`=1""",
			role,
		)
	]
