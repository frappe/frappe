# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json

import frappe
import requests


def log(data):
    telemetry_server = frappe.conf.get("telemetry_server")
    if not telemetry_server:
        return
    if not frappe.get_single_doc("Telemetry Settings").is_tracking_enabled(data.app):
        return

    frappe.enqueue(
        "frappe.telemetry.send_telemetry",
        data=data,
        queue="short",
        timeout=300,
        is_async=True,
    )


def send_telemetry(data):
    telemetry_server = frappe.conf.get("telemetry_server")
    if not telemetry_server:
        return

    try:
        requests.post(
            telemetry_server,
            data=json.dumps(data),
            headers={"Content-Type": "application/json"},
        )
    except Exception:
        pass