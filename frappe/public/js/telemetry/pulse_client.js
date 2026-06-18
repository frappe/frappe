// The JS half of the frappe pulse client. Wherever this runs, the backend pulse
// client (frappe.utils.telemetry.pulse.client) is present, so it's coupled to
// that backend's API — it owns the endpoint paths, CSRF handling, transport,
// enablement check, queue, and capture shaping. It stays free of any frontend
// framework (no vue, no desk globals in its logic), so desk, frappe-ui apps, and
// plain web pages can all use it with little or no glue.
//
// Defaults make it work out of the box; the options are the customization points
// (e.g. desk passes the boot-derived `enabled` to skip the is_enabled fetch;
// frappe-ui can pass its own `send`). Served as a public asset
// (/assets/frappe/js/telemetry/pulse_client.js) and exposed as
// `window.frappe.PulseClient` for classic web pages.

const API = "/api/method/frappe.utils.telemetry.pulse.client";
const ENDPOINTS = {
	capture: `${API}.bulk_capture`,
	guestCapture: `${API}.guest_capture`,
	isEnabled: `${API}.is_enabled`,
};

function defaultCsrfToken() {
	if (typeof window === "undefined") return undefined;
	return window.csrf_token || window.frappe?.csrf_token || undefined;
}

function defaultContext() {
	const boot = (typeof window !== "undefined" && window.frappe?.boot) || {};
	return { user: boot.telemetry_user, team: boot.telemetry_team };
}

export class PulseClient {
	constructor(options = {}) {
		const {
			guest = false,
			getContext,
			getCsrfToken,
			enabled,
			send,
			sendBeacon,
			flushInterval = 10000,
			maxQueueSize = 20,
			now,
		} = options;

		this.captureUrl = guest ? ENDPOINTS.guestCapture : ENDPOINTS.capture;
		this.getContext = getContext || defaultContext;
		this.getCsrfToken = getCsrfToken || defaultCsrfToken;
		// undefined => resolve via the is_enabled endpoint in init()
		this.enabledOverride = enabled;
		this.sendOverride = send;
		this.sendBeaconOverride = sendBeacon;
		this.flushInterval = flushInterval;
		this.maxQueueSize = maxQueueSize;
		this.now = now || (() => new Date().toISOString());

		this.enabled = false;
		this.eq = null;
		this.beforeUnloadAttached = false;
	}

	// Resolve enablement (cheap GET, false on any error so telemetry just stays
	// off on old frappe / network failure).
	isEnabled() {
		return fetch(ENDPOINTS.isEnabled, { method: "GET", credentials: "same-origin" })
			.then((r) => (r.ok ? r.json() : null))
			.then((data) => Boolean(data && data.message))
			.catch(() => false);
	}

	async init() {
		const enabled =
			this.enabledOverride !== undefined
				? Boolean(this.enabledOverride)
				: await this.isEnabled();
		this.setEnabled(enabled);
		if (enabled) this.start();
		return enabled;
	}

	setEnabled(enabled) {
		this.enabled = Boolean(enabled);
		if (!this.enabled) this.stop();
	}

	start() {
		if (!this.enabled || this.eq) return;
		this.eq = new QueueManager((events) => this._send(events), {
			flushInterval: this.flushInterval,
			maxQueueSize: this.maxQueueSize,
		});
		this._attachBeforeUnload();
	}

	capture(event_name, app, props) {
		if (!this.enabled) return;
		if (!this.eq) this.start();

		const { user, team } = this.getContext() || {};
		this.eq.add({
			event_name: event_name,
			app: app,
			properties: props,
			user: user,
			team: team,
			captured_at: this.now(),
		});
	}

	flush() {
		return this.eq?.flush();
	}

	stop() {
		this.eq?.stop();
		this.eq = null;
	}

	_send(events) {
		if (this.sendOverride) return this.sendOverride(events);

		const headers = { "Content-Type": "application/json" };
		const token = this.getCsrfToken();
		if (token) headers["X-Frappe-CSRF-Token"] = token;

		return fetch(this.captureUrl, {
			method: "POST",
			credentials: "same-origin",
			keepalive: true,
			headers: headers,
			body: JSON.stringify({ events: events }),
		}).then((r) => {
			if (!r.ok) throw new Error(`pulse capture failed: ${r.status}`);
		});
	}

	_sendBeacon(events) {
		if (this.sendBeaconOverride) return this.sendBeaconOverride(events);
		if (typeof navigator === "undefined" || !navigator.sendBeacon) return;

		const data = new FormData();
		data.append("events", JSON.stringify(events));
		// sendBeacon can't set headers, so the CSRF token rides in the body —
		// frappe reads it from form_dict["csrf_token"].
		const token = this.getCsrfToken();
		if (token) data.append("csrf_token", token);
		navigator.sendBeacon(this.captureUrl, data);
	}

	_attachBeforeUnload() {
		if (this.beforeUnloadAttached) return;
		if (typeof window === "undefined") return;
		this.beforeUnloadAttached = true;
		window.addEventListener("beforeunload", () => {
			const events = this.eq?.getBufferedEvents?.() || [];
			if (events.length) this._sendBeacon(events);
		});
	}
}

class QueueManager {
	constructor(flushCallback, options = {}) {
		this.flushCallback = flushCallback;
		this.queue = [];
		this.pendingBatch = null;
		this.retryAttempts = 0;
		this.maxRetries = 3;
		this.maxQueueSize = options.maxQueueSize || 20;
		this.flushInterval = options.flushInterval || 5000;
		this.timer = null;
		this.flushing = false;

		this.start();
	}

	getBufferedEvents() {
		const events = [];
		if (this.pendingBatch?.length) events.push(...this.pendingBatch);
		if (this.queue.length) events.push(...this.queue);
		return events;
	}

	start() {
		this.timer = setInterval(() => {
			if (this.queue.length || this.pendingBatch) this.flush();
		}, this.flushInterval);
	}

	add(event) {
		this.queue.push(event);

		if (this.queue.length >= this.maxQueueSize) {
			this.flush();
		}
	}

	async flush() {
		if (this.flushing) return;
		this.flushing = true;

		try {
			if (!this.pendingBatch) {
				if (!this.queue.length) return;
				this.pendingBatch = this.queue.splice(0, this.maxQueueSize);
				this.retryAttempts = 0;
			}

			try {
				await this.flushCallback(this.pendingBatch);
				this.pendingBatch = null;
				this.retryAttempts = 0;
			} catch (error) {
				this.retryAttempts++;
				if (this.retryAttempts > this.maxRetries) {
					this.pendingBatch = null;
					this.retryAttempts = 0;
				}
			}
		} finally {
			this.flushing = false;
		}
	}

	stop() {
		if (this.timer) {
			clearInterval(this.timer);
			this.timer = null;
		}
		this.flush();
	}
}

if (typeof window !== "undefined") {
	window.frappe = window.frappe || {};
	window.frappe.PulseClient = PulseClient;
}
