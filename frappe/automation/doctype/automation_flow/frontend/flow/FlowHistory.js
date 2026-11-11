/**
 * Undo and redo over whole-document snapshots (strings). Edits that land within `burstMs` of
 * each other, such as typing in a field, share one undo step.
 */
export class FlowHistory {
	constructor({ limit = 100, burstMs = 600 } = {}) {
		this.limit = limit;
		this.burstMs = burstMs;
		this.undos = [];
		this.redos = [];
		this.lastEditAt = 0;
	}

	get canUndo() {
		return this.undos.length > 0;
	}

	get canRedo() {
		return this.redos.length > 0;
	}

	/** An edit changed the document from `before`. */
	record(before, now = Date.now()) {
		if (now - this.lastEditAt >= this.burstMs) {
			this.undos.push(before);
			if (this.undos.length > this.limit) this.undos.shift();
		}
		this.lastEditAt = now;
		this.redos = [];
	}

	/** The snapshot to restore, or null when there is nothing to undo. */
	undo(current) {
		return this.step(this.undos, this.redos, current);
	}

	redo(current) {
		return this.step(this.redos, this.undos, current);
	}

	/** A save or a reload makes the old snapshots a different document's. */
	clear() {
		this.undos = [];
		this.redos = [];
		this.lastEditAt = 0;
	}

	step(from, to, current) {
		const snapshot = from.pop();
		if (snapshot === undefined) return null;
		to.push(current);
		this.lastEditAt = 0;
		return snapshot;
	}
}
