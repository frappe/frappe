import "../lib/posthog.js";

class TelemetryManager {
	constructor() {
		this.enabled = false;

		this.project_id = frappe.boot.posthog_project_id;
		this.telemetry_host = frappe.boot.posthog_host;

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
}

frappe.telemetry = new TelemetryManager();
frappe.telemetry.initialize();
