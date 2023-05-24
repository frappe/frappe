import "../lib/posthog.js";

class TelemetryManager {
	constructor() {
		this.enabled = false;

		this.project_id = frappe.boot.posthog_project_id;
		this.telemetry_host = frappe.boot.posthog_host;
		this.site_age = frappe.boot.telemetry_site_age;

		if (cint(frappe.boot.enable_telemetry) && this.project_id && this.telemetry_host) {
			this.enabled = true;
		}
	}

	initialize() {
		if (!this.enabled) return;
		try {
			posthog.init(this.project_id, {
				api_host: this.telemetry_host,
				autocapture: false,
				capture_pageview: false,
				capture_pageleave: false,
				advanced_disable_decide: true,
			});
			posthog.identify(frappe.boot.sitename);
			this.send_heartbeat();
			this.register_pageview_handler();
		} catch (e) {
			console.trace("Failed to initialize telemetry", e);
			this.enabled = false;
		}
	}

	capture(event, app) {
		if (!this.enabled) return;
		posthog.capture(`${app}_${event}`);
	}

	disable() {
		this.enabled = false;
		posthog.opt_out_capturing();
	}

	send_heartbeat() {
		const KEY = "ph_last_heartbeat";
		const now = frappe.datetime.system_datetime(true);
		const last = localStorage.getItem(KEY);

		if (!last || moment(now).diff(moment(last), "hours") > 12) {
			localStorage.setItem(KEY, now.toISOString());
			this.capture("heartbeat", "frappe");
		}
	}

	register_pageview_handler() {
		if (this.site_age && this.site_age > 5) {
			return;
		}

		frappe.router.on("change", () => {
			posthog.capture("$pageview");
		});
	}
}

frappe.telemetry = new TelemetryManager();
frappe.telemetry.initialize();
