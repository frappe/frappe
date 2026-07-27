import LayoutDialog from "./layout_dialog";
import ManageLayoutsDialog from "./manage_layouts_dialog";

/** Saved Layout data + menu items (rendered by the view switcher's submenu). */
export const ListFilterMenu = {
	/** Fetch layouts and restore the active one. The view switcher renders
	 *  the menu fresh from get_layout_menu_items() on every open, so no DOM
	 *  is built or synced here. */
	setup_layout_menu({ refetch = true, initial_setup = false } = {}) {
		const fetch_promise = refetch ? this.get_list_filters() : Promise.resolve();

		return fetch_promise.then(() => {
			if (!this._default_layout_snapshot) {
				this.capture_default_layout_state();
			}
			if (!initial_setup) {
				return this.restore_layout_from_route_signature({ refresh: true });
			}
		});
	},

	/** The saved-layouts submenu, as menu items: Default, then the global and
	 *  personal layouts (grouped), then the create/manage actions. Called by
	 *  the view switcher on every open, so active-state is always current. */
	get_layout_menu_items() {
		const active = String(this.active_layout_name || "default_layout");
		const layout_row = (layout) => ({
			label: __(layout.filter_name),
			selected: String(layout.name) === active,
			onclick: () => this.select_layout(layout.name, layout.filter_name),
		});

		const global_layouts = (this.filters || []).filter((f) => !f.for_user).map(layout_row);
		const user_layouts = (this.filters || [])
			.filter((f) => f.for_user === frappe.session.user)
			.map(layout_row);

		const items = [
			{
				label: this.default_layout_label,
				selected: active === "default_layout",
				onclick: () => this.select_layout("default_layout", this.default_layout_label),
			},
		];
		if (global_layouts.length) {
			items.push({ group: __("Global Layouts"), options: global_layouts });
		}
		if (user_layouts.length) {
			items.push({ group: __("Your Layouts"), options: user_layouts });
		}
		items.push({
			group: "",
			hide_label: true,
			options: [
				{
					label: __("Create Layout"),
					icon: "plus",
					onclick: () => this.open_layout_dialog(),
				},
				{
					label: __("Manage Layouts"),
					icon: "settings",
					onclick: () => this.open_manage_layouts_dialog(),
				},
			],
		});
		return items;
	},

	/** Normalize filter query params into a stable signature (matches list view URL encoding). */
	_signature_from_search_params(search_params) {
		const params = [];
		search_params.forEach((value, key) => {
			if (key === "_layout" || key === "reset_filters") return;
			params.push([key, value]);
		});
		params.sort((a, b) =>
			a[0] === b[0] ? String(a[1]).localeCompare(String(b[1])) : a[0].localeCompare(b[0])
		);
		return params.map(([key, value]) => `${key}=${value}`).join("&");
	},

	/** Normalize filter values so layout signatures match live list filters. */
	normalize_filter_value(operator, value) {
		if (value === null || value === undefined) return value;

		if (operator === "like" && typeof value === "string") {
			const stripped = value.replace(/^%+|%+$/g, "");
			return stripped ? `%${stripped}%` : value;
		}

		if (operator === "=" && typeof value === "string") {
			return value.replace(/^%+|%+$/g, "");
		}

		return value;
	},

	/** Build signature from current filters (same encoding as list view URL). */
	get_route_signature() {
		const lv = this.list_view;
		if (lv?.get_search_params) {
			return this._signature_from_search_params(lv.get_search_params());
		}
		return this._signature_from_search_params(new URL(window.location.href).searchParams);
	},

	/** Build signature from saved filter tuples (used when creating/updating layouts). */
	get_route_signature_from_filters(filters) {
		const lv = this.list_view;
		const search_params = new URLSearchParams();
		(filters || []).forEach((filter) => {
			const [doctype, field, operator, value] = filter;
			const query_key = doctype === lv.doctype ? field : `${doctype}.${field}`;
			const normalized_value = this.normalize_filter_value(operator, value);
			const query_value =
				operator === "=" ? normalized_value : JSON.stringify([operator, normalized_value]);
			search_params.append(query_key, query_value);
		});
		return this._signature_from_search_params(search_params);
	},

	/** Return stored or computed route signature for a layout. */
	get_layout_route_signature(layout) {
		if (layout?._route_signature) return layout._route_signature;
		const stored = layout?.route_signature;
		if (stored) return stored;
		return this.get_route_signature_from_filters(this.parse_layout_filters(layout));
	},

	/** Saved layout name from user settings (last manual or auto selection). */
	get_saved_active_layout_name() {
		const lv = this.list_view;
		return frappe.get_user_settings(lv.doctype, lv.view_name)?.active_layout_name || "";
	},

	/** Persist last active layout for normal reopen (not used when URL carries navigation filters). */
	save_active_layout_preference(name) {
		const lv = this.list_view;
		frappe.model.user_settings.save(lv.doctype, lv.view_name, {
			active_layout_name: name === "default_layout" ? "" : name,
		});
	},

	set_active_layout(layout) {
		this.active_layout_name = layout.name;
		this.active_layout_label = layout.filter_name;
	},

	set_active_default_layout() {
		this.active_layout_name = "default_layout";
		this.active_layout_label = this.default_layout_label;
	},

	find_layout_by_name(name) {
		return (this.filters || []).find((layout) => layout.name === name) || null;
	},

	/** Match a saved layout to the current filter signature. */
	find_layout_by_signature(signature) {
		if (!signature) return null;
		return (
			(this.filters || []).find((layout) => {
				const layout_signature = this.get_layout_route_signature(layout);
				return layout_signature && layout_signature === signature;
			}) || null
		);
	},

	/** Pick active layout by matching URL filter signature; else Default Layout. */
	restore_layout_from_route_signature({ refresh = true } = {}) {
		const finish = () => {
			this._initial_layout_restored = true;
			// the view switcher's trigger shows the active layout name
			this.list_view.views_list?.refresh_trigger?.();
		};

		if (this._user_selected_layout) {
			finish();
			return Promise.resolve();
		}

		const signature = this.get_route_signature();

		// No URL filters → last saved layout preference, else Default Layout.
		if (!signature) {
			const saved_name = this.get_saved_active_layout_name();
			const saved_layout = saved_name ? this.find_layout_by_name(saved_name) : null;
			if (saved_layout) {
				this.set_active_layout(saved_layout);
				return this.apply_saved_layout(saved_layout, { refresh }).then(finish, finish);
			}
			this.set_active_default_layout();
			finish();
			return Promise.resolve();
		}

		const matched_layout = this.find_layout_by_signature(signature);

		if (!matched_layout) {
			this.set_active_default_layout();
			finish();
			return Promise.resolve();
		}

		this.set_active_layout(matched_layout);
		this.save_active_layout_preference(matched_layout.name);
		return this.apply_saved_layout(matched_layout, { refresh }).then(finish, finish);
	},

	/** Remember the selected layout and apply its state. The switcher's menu
	 *  shows the new selection by itself — it renders fresh on every open. */
	select_layout(name, label) {
		if (name === this.active_layout_name) return Promise.resolve();

		if (name !== "default_layout" && this.active_layout_name === "default_layout") {
			this.capture_default_layout_state({ from_live: true });
		}

		this.active_layout_name = name;
		this.active_layout_label = label;
		this._user_selected_layout = true;
		this.save_active_layout_preference(name);
		// the view switcher's trigger shows the active layout name
		this.list_view.views_list?.refresh_trigger?.();

		const apply_promise =
			name === "default_layout"
				? this.apply_default_layout()
				: this.apply_saved_layout((this.filters || []).find((row) => row.name === name));

		return Promise.resolve(apply_promise);
	},

	/** Snapshot default layout state from user settings or the live list view. */
	capture_default_layout_state({ from_live = false } = {}) {
		const lv = this.list_view;
		let filters = [];
		let sort_by;
		let sort_order;

		if (from_live && lv.filter_area) {
			filters = (lv.filter_area.get() || []).map((f) => f.slice(0, 4));
			sort_by = lv.sort_by;
			sort_order = lv.sort_order;
		} else {
			const settings = frappe.get_user_settings(lv.doctype, lv.view_name) || {};
			if (Array.isArray(settings.filters)) {
				filters = lv.validate_filters(settings.filters);
			} else {
				filters = (lv.settings.filters || []).map((f) => {
					if (f.length === 3) {
						return [lv.doctype, f[0], f[1], f[2]];
					}
					return f;
				});
			}
			sort_by = settings.sort_by || lv.meta?.sort_field || "creation";
			sort_order = settings.sort_order || lv.meta?.sort_order || "desc";
		}

		this._default_layout_snapshot = { filters, sort_by, sort_order };
	},

	/** Restore filters, sort, and columns from user settings (default layout). */
	apply_default_layout({ refresh = true } = {}) {
		const lv = this.list_view;
		lv.user_settings = frappe.get_user_settings(lv.doctype);
		// Keep snapshot captured when leaving default; user settings may hold saved-layout filters after refresh.
		if (!this._default_layout_snapshot) {
			this.capture_default_layout_state();
		}

		const { filters, sort_by, sort_order } = this._default_layout_snapshot;

		return this.apply_layout_state({
			filters,
			sort_by,
			sort_order,
			columns: null,
			refresh,
		});
	},

	/** Apply filters, sort, and columns from a saved layout document. */
	apply_saved_layout(layout, { refresh = true } = {}) {
		if (!layout) return Promise.resolve();

		return this.apply_layout_state({
			filters: this.parse_layout_filters(layout),
			sort_by: layout.sort_field || this.list_view.meta?.sort_field || "creation",
			sort_order: layout.sort_order || this.list_view.meta?.sort_order || "desc",
			columns: this.get_layout_columns(layout),
			refresh,
		});
	},

	parse_layout_filters(layout) {
		if (layout?._parsed_filters) return layout._parsed_filters;
		try {
			const filters = JSON.parse(layout?.filters || "[]");
			const parsed = Array.isArray(filters) ? this.list_view.validate_filters(filters) : [];
			if (layout) layout._parsed_filters = parsed;
			return parsed;
		} catch {
			return [];
		}
	},

	/** Apply filters, sort, and columns without persisting anything. */
	apply_layout_state({ filters, sort_by, sort_order, columns, refresh = true }) {
		const lv = this.list_view;
		this._applying_layout = true;
		lv.last_args = null;
		lv.sort_by = sort_by;
		lv.sort_order = sort_order;
		lv.sort_selector?.set_value(sort_by, sort_order);

		const apply_columns = () => {
			lv.column_max_widths = {};
			if (columns?.length) {
				columns.forEach((col) => {
					if (col.width) {
						lv.column_max_widths[col.fieldname] = cint(col.width);
					}
				});
				return lv.setup_columns(columns);
			}
			return lv.setup_columns();
		};

		const finish = () => {
			this._applying_layout = false;
		};

		const filter_area = lv.filter_area;
		if (!filter_area) {
			lv.filters = filters || [];
			return apply_columns().then(() => {
				if (refresh) {
					return lv.refresh(true).then(finish, finish);
				}
				finish();
			}, finish);
		}

		filter_area.trigger_refresh = false;
		return filter_area
			.clear(false)
			.then(() => filter_area.set(filters || []))
			.then(() => {
				filter_area.trigger_refresh = true;
				lv.filters = filters || [];
				return apply_columns().then(() => {
					if (refresh) return lv.refresh(true);
				});
			})
			.then(finish, finish);
	},

	/** Build current visible columns state for layout persistence. */
	get_current_columns_state() {
		const columns = this.list_view.columns || [];
		return columns
			.filter((col) => col.type !== "Tag")
			.map((col) => {
				if (col.type === "Status") {
					return {
						fieldname: "status_field",
						label: __("Status"),
						width:
							this.list_view.column_max_widths?.status_field ||
							col.df?.width ||
							null,
					};
				}
				const fieldname = col.df?.fieldname;
				if (!fieldname) return null;
				return {
					fieldname,
					label: col.df?.label || fieldname,
					width: this.list_view.column_max_widths?.[fieldname] || col.df?.width || null,
				};
			})
			.filter(Boolean);
	},

	open_manage_layouts_dialog() {
		new ManageLayoutsDialog({ list_filter: this });
	},

	/** Open shared create/edit/duplicate layout dialog. */
	open_layout_dialog(layout = null, { duplicate_from = null } = {}) {
		new LayoutDialog({
			list_view: this.list_view,
			layout,
			duplicate_from,
			on_save: () => this.setup_layout_menu({ refetch: true }),
		});
	},
};
