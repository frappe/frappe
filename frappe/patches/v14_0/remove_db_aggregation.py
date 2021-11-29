from frappe.query_builder import DocType
import frappe
import re


def execute():
    sub_aggregation()


def sub_aggregation():
    server_scripts = DocType("Server Script")
    scripts = (
        frappe.qb.from_(server_scripts)
        .where(
            server_scripts.script.like("%frappe.db.max%")
            | server_scripts.script.like("%frappe.db.min%")
            | server_scripts.script.like("%frappe.db.sum%")
            | server_scripts.script.like("%frappe.db.avg%")
        )
        .select("name", "script")
        .run(as_dict=True)
    )

    def _sub_aggregation(scripts, function, substitution):
        for script in scripts:
            script.update(
                {"script": re.sub(f"{function}", f"{substitution}", script["script"])}
            )

    _sub_aggregation(scripts, "frappe.db.max", "frappe.qb.max")
    _sub_aggregation(scripts, "frappe.db.min", "frappe.qb.min")
    _sub_aggregation(scripts, "frappe.db.sum", "frappe.qb.sum")
    _sub_aggregation(scripts, "frappe.db.avg", "frappe.qb.avg")

    for script in scripts:
        frappe.db.update(
            "Server Script", {"name": script["name"]}, "script", script["script"]
        )
