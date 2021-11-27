import frappe
import re


def execute():
    _sub_aggregation("frappe.db.max", "frappe.qb.max")
    _sub_aggregation("frappe.db.min", "frappe.qb.min")
    _sub_aggregation("frappe.db.sum", "frappe.qb.sum")
    _sub_aggregation("frappe.db.avg", "frappe.qb.avg")


def _sub_aggregation(function, subtitution):
    scripts = frappe.get_all(
        "Server Script",
        filters={"script": ("like", f"%{function}%")},
        fields=["name", "script"],
    )
    for script in scripts:
        script.update(
            {"script": re.sub(f"{function}", f"{subtitution}", script["script"])}
        )
    for script in scripts:
        frappe.db.update(
            "Server Script", {"name": script["name"]}, "script", script["script"]
        )
