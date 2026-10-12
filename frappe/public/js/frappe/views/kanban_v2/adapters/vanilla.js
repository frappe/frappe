// frappe.kanban_v2.KanbanVanilla: mounts a KanbanCore into wrapper; all logic lives in the core.
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

	// the KanbanCore, for events, state and selection
	get engine() {
		return this.core;
	}
}
