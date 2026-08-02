/**
 * Vanilla adapter — the `frappe.kanban_v2.KanbanVanilla` entry point.
 * A thin wrapper: constructs a KanbanCore, mounts it, and exposes a small
 * imperative surface (refresh / destroy / engine). All logic lives in the core.
 */
import { KanbanCore } from "../core/kanban_core";

export class KanbanVanilla {
	constructor(wrapper, options) {
		this.core = new KanbanCore(options);
		this.core.mount(wrapper);
	}

	refresh() {
		return this.core.reload();
	}

	destroy() {
		this.core.destroy();
	}

	/** Escape hatch for advanced callers (events, state, selection). */
	get engine() {
		return this.core;
	}
}
