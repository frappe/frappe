// Minimal event bus. No dependencies — the core stays framework-agnostic.
export class EventBus {
	constructor() {
		this.handlers = new Map();
	}

	on(event, cb) {
		let set = this.handlers.get(event);
		if (!set) {
			set = new Set();
			this.handlers.set(event, set);
		}
		set.add(cb);
		return () => set.delete(cb);
	}

	emit(event, ...args) {
		const set = this.handlers.get(event);
		if (!set) return;
		for (const cb of set) cb(...args);
	}

	clear() {
		this.handlers.clear();
	}
}
