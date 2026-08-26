from functools import lru_cache

import frappe
from frappe.tests.microbenchmarks.utils import NanoBenchmark


def bench_get_value_simple():
	status = []
	for role in get_all_roles():
		status.append(frappe.db.get_value("Role", role, "disabled"))


def bench_get_value_with_dict_filters():
	return frappe.db.get_value("Role", {"creation": (">", "2020-01-01 00:00:00")}, "disabled")


def bench_get_value_with_list_filters():
	return frappe.db.get_value("Role", ["creation", ">", "2020-01-01 00:00:00"], "*")


def bench_get_cached_value_simple():
	status = []
	for _ in range(10):
		for role in get_all_roles():
			status.append(frappe.db.get_value("Role", role, "disabled", cache=True))


def bench_set_value_simple():
	return frappe.db.set_value("Role", "Guest", "disabled", 0)  # This is a noop to DB.


def bench_delete_value_simple():
	return frappe.db.delete("Role", {"name": "Not_GUEST"})  # This is a noop to DB.


def bench_empty_transaction_cycling():
	frappe.db.rollback()
	frappe.db.commit()


def bench_get_single_value():
	country = frappe.db.get_single_value("System Settings", "country", cache=False)
	# Requires Casting
	telemetry = frappe.db.get_single_value("System Settings", "enable_telemetry", cache=False)
	return country, telemetry


def bench_select_star():
	kwargs = [{}, {"as_list": True}, {"as_dict": True}]
	results = []
	for kw in kwargs:
		results.append(frappe.db.sql("select * from tabRole order by creation limit 10", kw))

	return results


def bench_sql_select_many_rows():
	return frappe.db.sql("select * from `tabDocField` order by creation limit 1000")


@lru_cache
def get_all_roles():
	return frappe.get_all("Role", order_by="creation asc", limit=10, pluck="name")
