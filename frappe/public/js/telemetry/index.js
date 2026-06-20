import { pulse_provider } from "./pulse.js";

class TelemetryManager {
	constructor() {
		this.enabled = frappe.boot.enable_telemetry || false;
		this.pulse_available = Boolean(frappe.boot.telemetry_provider?.includes("pulse"));

		this.init_providers();
	}

	init_providers() {
		this.providers = [];

		// Initialize pulse provider
		pulse_provider.init();
		if (pulse_provider.enabled) {
			this.providers.push(pulse_provider);
		}
	}

	capture(event, app, props) {
		if (!this.enabled) return;

		for (let provider of this.providers) {
			provider.capture(event, app, props);
		}
	}

	disable() {
		this.enabled = false;
		this.providers = [];
	}

	can_enable() {
		let sentry_available = Boolean(frappe.boot.sentry_dsn);
		return this.pulse_available || sentry_available;
	}
}

frappe.telemetry = new TelemetryManager();
