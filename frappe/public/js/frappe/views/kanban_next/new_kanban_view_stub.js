frappe.provide("frappe.views");

/**
 * Thin shim registered in list.bundle.js (always loaded).
 * The full page logic (NewKanbanPage, SELECT_STYLES, swimlanes) lives in
 * kanban_next.bundle.js so the default bundle stays lean.
 */
frappe.views.NewKanbanView = class NewKanbanView {
	static load_last_view() {
		return frappe.views.KanbanView.load_last_view();
	}

	constructor(opts) {
		this.doctype = opts.doctype;
		this.parent = opts.parent;
		this.page = this.parent.page;
		this.show();
	}

	/** Resolve board from route (or last/first board), then mount the engine. */
	show() {
		return frappe.views.KanbanView.get_kanbans(this.doctype).then((kanbans) => {
			frappe.route_options = {};
			if (!kanbans.length) {
				return frappe.views.KanbanView.show_kanban_dialog(this.doctype, true);
			}
			if (frappe.get_route().length !== 4) {
				const last_board = frappe.get_user_settings(this.doctype)["Kanban"]
					?.last_kanban_board;
				const names = (kanbans || []).map((k) => k.name || k);
				if (last_board && names.includes(last_board)) {
					frappe.set_route("List", this.doctype, "Kanban", last_board);
					return;
				}
				const first = kanbans[0];
				frappe.set_route("List", this.doctype, "Kanban", first.name || first);
				return;
			}
			// Load the full page bundle on demand, then mount.
			return new Promise((resolve) => frappe.require("kanban_next.bundle.js", resolve)).then(
				() => {
					if (!this._kanban) {
						this._kanban = new frappe.views.NewKanbanPage(this.parent);
					}
					return this._kanban.load_from_route();
				}
			);
		});
	}
};
