class PulseProvider {
	constructor() {
		this.enabled = false;
		this.eq = null;
	}

	is_enabled() {
		return frappe.boot.telemetry_provider?.includes("pulse") && frappe.boot.enable_telemetry;
	}

	init() {
		if (!this.is_enabled()) return;
		this.enabled = true;

		try {
			this.eq = new QueueManager((events) => this.sendEvents(events), {
				flushInterval: 10000,
			});

			// Send remaining events on unload
			window.addEventListener("beforeunload", () => {
				const events = this.eq?.getBufferedEvents?.() || [];
				if (events.length) this.sendBeacon(events);
			});
		} catch (error) {
			// ignore errors
		}
	}

	capture(event, app, props) {
		if (!this.enabled) return;

		this.eq.add({
			event_name: event,
			app: app,
			properties: props,
			user: frappe.session?.user,
			captured_at: new Date().toISOString(),
		});
	}

	sendEvents(events) {
		// Return a Promise so QueueManager can retry on failure.
		return new Promise((resolve, reject) => {
			try {
				frappe.call({
					method: "frappe.utils.telemetry.pulse.client.bulk_capture",
					args: { events },
					type: "POST",
					no_spinner: true,
					freeze: false,
					callback: () => resolve(),
					error: (error) => reject(error),
				});
			} catch (error) {
				reject(error);
			}
		});
	}

	sendBeacon(events) {
		try {
			if (navigator.sendBeacon) {
				const url = "/api/method/frappe.utils.telemetry.pulse.client.bulk_capture";
				const data = new FormData();
				data.append("events", JSON.stringify(events));
				navigator.sendBeacon(url, data);
			}
		} catch (error) {
			// ignore errors
		}
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

export const pulse_provider = new PulseProvider();
