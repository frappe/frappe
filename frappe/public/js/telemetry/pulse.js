// The pulse client lives in one place — pulse's CDN — and desk loads it at
// runtime, same as frappe-ui apps. There's no bundled framework copy to keep in
// sync. Telemetry already depends on pulse being reachable (that's where events
// POST), so loading the client from there adds no new failure mode.
const DEFAULT_PULSE_CLIENT_URL = "https://pulse.m.frappe.cloud/assets/pulse/js/pulse_client.js";

class PulseProvider {
	constructor() {
		this.enabled = false;
		this.client = null;
	}

	is_enabled() {
		return frappe.boot.telemetry_provider?.includes("pulse") && frappe.boot.enable_telemetry;
	}

	async init() {
		if (!this.is_enabled()) return;
		this.enabled = true;

		try {
			const t = frappe.boot.telemetry || {};
			// A runtime variable (not a string literal) so the bundler leaves this as
			// a real runtime import of the remote module instead of trying to bundle it.
			const url = t.client_url || DEFAULT_PULSE_CLIENT_URL;
			const mod = await import(url);
			this.client = new mod.PulseClient({
				host: t.host,
				apiKey: t.key,
				site: t.site,
				enabled: t.enabled,
				// user/team come from boot.telemetry via the client's default context
			});
			this.client.init();
			this.register_pageview_handler();
		} catch (error) {
			// ignore errors
		}
	}

	register_pageview_handler() {
		const site_age = frappe.boot.telemetry_site_age;
		if (site_age && site_age > 15) {
			return;
		}

		frappe.router.on("change", () => {
			this.capture("pageview", "frappe", { route: this.scrub_route(frappe.get_route()) });
		});
	}

	scrub_route(route) {
		if (!route?.length) return "";

		// Document names can be PII. Replace them with a placeholder.
		// In a Form route (e.g. ["Form", "Sales Order", "SO-0001"]) the
		// document name is at index 2.
		if (route[0] === "Form" && route.length >= 3 && route[2] !== route[1]) {
			route = [...route];
			route[2] = "*";
		}

		return route.join("/");
	}

	capture(event, app, props) {
		if (!this.enabled) return;
		this.client?.capture(event, app, props);
	}
}

export const pulse_provider = new PulseProvider();
