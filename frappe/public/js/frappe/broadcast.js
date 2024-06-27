// Note: This is not public API.
// It's a thin layer over BroadcastChannel, you can implement your own if you need one.

class BroadcastManager {
	constructor() {
		this.channel = new BroadcastChannel("frappe");
		this._event_handlers = {};
		this.channel.onmessage = (message) => {
			let { data, event } = message.data;
			if (!event) return; // not created by this wrapper

			let handlers = this._event_handlers[event] || [];
			handlers.forEach((handler) => {
				handler(data);
			});
		};
	}

	emit(event, data) {
		this.channel.postMessage({ event, data });
	}

	on(event, callback) {
		if (!this._event_handlers[event]) {
			this._event_handlers[event] = [];
		}
		this._event_handlers[event].push(callback);
	}

	off(event, callback = null) {
		if (callback) {
			let handlers = this._event_handlers[event];
			if (!handlers) return;
			this._event_handlers[event] = handlers.filter((h) => h !== callback);
		} else {
			this._event_handlers[event] = [];
		}
	}
}

frappe.broadcast = new BroadcastManager();
