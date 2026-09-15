// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.views.list_view");

window.cur_list = null;
frappe.views.ListFactory = class ListFactory extends frappe.views.Factory {
	make(route) {
		const me = this;
		const doctype = route[1];

		// List / Gantt / Kanban / etc
		let view_name = frappe.utils.to_title_case(route[2] || "List");

		// File is a special view
		if (doctype == "File" && !["Report", "Dashboard"].includes(view_name)) {
			view_name = "File";
		}

		// Kanban engine is chosen per board (Kanban Board → "Use Kanban v2").
		// The v2 bundle loads on demand so the default bundle stays lean.
		if (view_name === "Kanban") {
			// Resolve the board into the route first (may redirect to the last/first
			// board). Once route[3] is known we pick the engine for that board.
			if (frappe.views.KanbanView.load_last_view()) return;
			frappe.views.get_kanban_engine(route[3]).then((use_v2) => {
				frappe.provide("frappe.views.list_view." + doctype);
				const build = (View) => {
					frappe.views.list_view[me.page_name] = new View({
						doctype,
						parent: me.make_page(true, me.page_name, null),
					});
					me.set_cur_list();
				};
				if (use_v2) {
					frappe.require("kanban.bundle.js", () => build(frappe.views.KanbanV2View));
				} else {
					build(frappe.views.KanbanView);
				}
			});
			return;
		}

		let view_class = frappe.views[view_name + "View"];
		if (!view_class) view_class = frappe.views.ListView;

		if (view_class && view_class.load_last_view && view_class.load_last_view()) {
			// view can have custom routing logic
			return;
		}

		frappe.provide("frappe.views.list_view." + doctype);

		const hide_sidebar = true;

		frappe.views.list_view[me.page_name] = new view_class({
			doctype: doctype,
			parent: me.make_page(true, me.page_name, hide_sidebar ? null : "Right"),
		});

		me.set_cur_list();
	}

	before_show() {
		if (this.re_route_to_view()) {
			return false;
		}
	}

	on_show() {
		this.set_cur_list();
		if (cur_list) cur_list.show();
	}

	re_route_to_view() {
		const doctype = this.route[1];
		const last_route = frappe.route_history.slice(-2)[0];
		if (
			this.route[0] === "List" &&
			this.route.length === 2 &&
			frappe.views.list_view[doctype] &&
			last_route &&
			last_route[0] === "List" &&
			last_route[1] === doctype
		) {
			// last route same as this route, so going back.
			// this happens because /desk/List/Item will redirect to /desk/List/Item/List
			// while coming from back button, the last 2 routes will be same, so
			// we know user is coming in the reverse direction (via back button)

			// example:
			// Step 1: /desk/List/Item redirects to /desk/List/Item/List
			// Step 2: User hits "back" comes back to /desk/List/Item
			// Step 3: Now we cannot send the user back to /desk/List/Item/List so go back one more step
			window.history.go(-1);
			return true;
		}
	}

	set_cur_list() {
		cur_list = frappe.views.list_view[this.page_name];
		if (cur_list && cur_list.doctype !== this.route[1]) {
			// changing...
			window.cur_list = null;
		}
	}
};

// board name -> boolean (uses Kanban v2). Primed by KanbanView.get_kanbans so
// board-to-board switches never re-fetch; a board's form clears its entry on save.
frappe.views._kanban_engine_cache = frappe.views._kanban_engine_cache || {};

/**
 * Resolve which Kanban engine a board uses: true = Kanban v2, false = classic.
 * Reads the board's `use_kanban_v2` flag (default off) with a small per-session
 * cache. Unset/unknown boards fall back to the classic engine.
 */
frappe.views.get_kanban_engine = function (board) {
	if (!board) return Promise.resolve(false);
	if (board in frappe.views._kanban_engine_cache) {
		return Promise.resolve(frappe.views._kanban_engine_cache[board]);
	}
	return frappe.db.get_value("Kanban Board", board, "use_kanban_v2").then((r) => {
		const use_v2 = !!cint(r && r.message && r.message.use_kanban_v2);
		frappe.views._kanban_engine_cache[board] = use_v2;
		return use_v2;
	});
};
