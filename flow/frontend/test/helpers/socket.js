// a socket.io stand-in: listeners are called by the test, subscribe acks at once
export function fakeSocket({ subscribed = true } = {}) {
	const listeners = new Map();
	return {
		subscribed, // the next subscribe's answer
		emitted: [],
		on(name, fn) {
			listeners.set(name, fn);
		},
		off(name) {
			listeners.delete(name);
		},
		emit(name, ...args) {
			this.emitted.push([name, ...args.filter((a) => typeof a !== "function")]);
			const ack = args.find((a) => typeof a === "function");
			if (name === "flow:subscribe" && ack)
				queueMicrotask(() => ack({ subscribed: this.subscribed }));
		},
		fire(name, payload) {
			listeners.get(name)?.(payload);
		},
		has(name) {
			return listeners.has(name);
		},
	};
}
