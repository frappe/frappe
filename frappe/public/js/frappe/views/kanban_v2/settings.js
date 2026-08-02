/**
 * Per-doctype Kanban customization registry.
 *
 * Owning app (doctype folder `{doctype}_kanban.js`) usually assigns once:
 *   frappe.kanban_v2.settings["Task"] = {
 *     card_context_menu() { ... },
 *     bulk_actions() { ... },
 *   };
 *
 * Another app (hooks `doctype_kanban_js`) should extend so the base stays:
 *   frappe.kanban_v2.extend_settings("Task", (super_) => ({
 *     card_context_menu(card, page) {
 *       return [
 *         ...(super_.card_context_menu?.(card, page) || []),
 *         { label: __("My Action"), onclick: () => {} },
 *       ];
 *     },
 *     bulk_actions(ids, page) {
 *       return [
 *         ...(super_.bulk_actions?.(ids, page) || []),
 *         { label: __("My Bulk"), onclick(ids, page, done) {} },
 *       ];
 *     },
 *     select_styles: { ...super_.select_styles, blocked: "red" },
 *   }));
 *
 * Plain-object form auto-merges common keys (menu / bulk items append; styles /
 * callbacks / options / boards shallow-merge):
 *   frappe.kanban_v2.extend_settings("Task", {
 *     card_context_menu(card, page) {
 *       return [{ label: __("My Action"), onclick: () => {} }];
 *     },
 *     bulk_actions(ids, page) {
 *       return [{ label: __("My Bulk"), onclick(ids, page, done) {} }];
 *     },
 *   });
 */
frappe.provide("frappe.kanban_v2.settings");

/**
 * Layer new Kanban settings on top of whatever is already registered for the
 * doctype. Pass a function to get the previous layer as `super_` (like
 * Python's super()), or a plain object for an automatic merge.
 */
frappe.kanban_v2.extend_settings = function (doctype, patch) {
	const parent = copy_kanban_settings(frappe.kanban_v2.settings[doctype] || {});
	const next =
		typeof patch === "function"
			? patch(parent) || {}
			: merge_kanban_settings(parent, patch || {});
	frappe.kanban_v2.settings[doctype] = next;
	return next;
};

/** Shallow copy of settings plus nested maps we merge later. */
function copy_kanban_settings(src) {
	return {
		...src,
		callbacks: { ...(src.callbacks || {}) },
		select_styles: { ...(src.select_styles || {}) },
		options: { ...(src.options || {}) },
		boards: { ...(src.boards || {}) },
	};
}

/**
 * Merge a patch onto parent. `card_context_menu` / `bulk_actions` run parent
 * then child and concatenate items; callbacks / select_styles / options
 * shallow-merge; each `boards[name]` is merged the same way.
 */
function merge_kanban_settings(parent, patch) {
	const out = { ...parent, ...patch };

	compose_item_list(out, parent, patch, "card_context_menu");
	compose_item_list(out, parent, patch, "bulk_actions");

	if (patch.callbacks || parent.callbacks) {
		out.callbacks = { ...(parent.callbacks || {}), ...(patch.callbacks || {}) };
	}
	if (patch.select_styles || parent.select_styles) {
		out.select_styles = { ...(parent.select_styles || {}), ...(patch.select_styles || {}) };
	}
	if (patch.options || parent.options) {
		out.options = { ...(parent.options || {}), ...(patch.options || {}) };
	}

	if (patch.boards || parent.boards) {
		out.boards = { ...(parent.boards || {}) };
		for (const [name, board_patch] of Object.entries(patch.boards || {})) {
			out.boards[name] = merge_kanban_settings(out.boards[name] || {}, board_patch);
		}
	}

	return out;
}

/** Compose parent+child list-returning hooks (context menu, bulk actions). */
function compose_item_list(out, parent, patch, key) {
	if (patch[key] && parent[key]) {
		const base = parent[key];
		const child = patch[key];
		out[key] = (...args) => [...(base(...args) || []), ...(child(...args) || [])];
	}
}
