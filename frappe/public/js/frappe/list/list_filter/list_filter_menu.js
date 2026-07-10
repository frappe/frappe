import LayoutDialog from "./layout_dialog";
import ManageLayoutsDialog from "./manage_layouts_dialog";

/** Saved Layout menu rendering and layout dialog actions. */
export const ListFilterMenu = {
	/** Group label shown in page inner button for saved layouts menu. */
	get saved_layout_group_label() {
		return __("Default Layout");
	},

	/** Create the Saved Layouts button and populate the dropdown menu. */
	setup_layout_menu({ refetch = true, initial_setup = false } = {}) {
		if (frappe.is_mobile()) return Promise.resolve();

		this.ensure_layout_menu_group();

		const fetch_promise = refetch ? this.get_list_filters() : Promise.resolve();

		return fetch_promise
			.then(() => {
				if (!this._default_layout_snapshot) {
					this.capture_default_layout_state();
				}
				if (!initial_setup) {
					return this.restore_layout_from_route_signature({ refresh: true });
				}
			})
			.then(() => {
				if (!initial_setup) {
					this.update_layout_menu_selection({ rerender_menu: true });
				}
			});
	},

	/** Create the inner button group once (first item is replaced on render). */
	ensure_layout_menu_group() {
		if (this.layout_menu_group) return;

		this.list_view.page.add_inner_button(
			this.default_layout_label,
			() => {},
			this.saved_layout_group_label
		);
		this.layout_menu_group = this.list_view.page.get_inner_group_button(
			this.saved_layout_group_label
		);
	},

	/** Live dropdown menu element (do not cache items — menu is re-rendered). */
	get_layout_menu() {
		this.ensure_layout_menu_group();
		return this.layout_menu_group.find(".dropdown-menu");
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
			this.update_layout_menu_selection({ rerender_menu: true });
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

	/** Render default, global, user, and action rows in the dropdown menu. */
	render_saved_filters() {
		const $menu = this.get_layout_menu();
		$menu.empty();

		const $default_item = this.filter_template({
			name: "default_layout",
			filter_name: this.default_layout_label,
		});
		$default_item.find(".dropdown-item").on("click", (e) => {
			e.preventDefault();
			this.select_layout("default_layout", this.default_layout_label);
		});
		$menu.append($default_item);
		$menu.append('<li class="dropdown-divider"></li>');

		const global_filters = (this.filters || []).filter((filter) => !filter.for_user);
		const user_filters = (this.filters || []).filter(
			(filter) => filter.for_user === frappe.session.user
		);

		if (global_filters.length) {
			$menu.append(`<li class="dropdown-header">${__("Global Layouts")}</li>`);
			this.append_filter_items($menu, global_filters);
		}

		if (user_filters.length) {
			if (global_filters.length) {
				$menu.append('<li class="dropdown-divider"></li>');
			}
			$menu.append(`<li class="dropdown-header">${__("Your Layouts")}</li>`);
			this.append_filter_items($menu, user_filters);
		}

		if (global_filters.length || user_filters.length) {
			$menu.append('<li class="dropdown-divider"></li>');
		}

		this.append_layout_action_items($menu);
	},

	/** Append saved layout rows and update button label on selection. */
	append_filter_items($menu, filters) {
		(filters || []).forEach((filter) => {
			const $item = this.filter_template(filter);
			$item.find(".dropdown-item").on("click", (e) => {
				e.preventDefault();
				this.select_layout(filter.name, filter.filter_name);
			});
			$menu.append($item);
		});
	},

	/** Remember selected layout, apply its state, and reflect it on the button. */
	select_layout(name, label) {
		if (name === this.active_layout_name) return Promise.resolve();

		if (name !== "default_layout" && this.active_layout_name === "default_layout") {
			this.capture_default_layout_state({ from_live: true });
		}

		this.active_layout_name = name;
		this.active_layout_label = label;
		this._user_selected_layout = true;
		this.save_active_layout_preference(name);
		this.update_layout_menu_selection();

		const apply_promise =
			name === "default_layout"
				? this.apply_default_layout()
				: this.apply_saved_layout((this.filters || []).find((row) => row.name === name));

		return Promise.resolve(apply_promise).then(() => {
			this.update_active_filter_label();
			this.update_active_filter_indicators();
		});
	},

	/** Sync button label and menu tick with the active layout. */
	update_layout_menu_selection({ rerender_menu = false } = {}) {
		if (!this.layout_menu_group) return;

		this.update_active_filter_label();

		if (rerender_menu) {
			this.render_saved_filters();
		} else {
			this.update_active_filter_indicators();
		}
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
				lv.setup_columns(columns);
			} else {
				lv.setup_columns();
			}
		};

		const finish = () => {
			this._applying_layout = false;
		};

		const filter_area = lv.filter_area;
		if (!filter_area) {
			lv.filters = filters || [];
			apply_columns();
			if (refresh) {
				return lv.refresh(true).then(finish, finish);
			}
			finish();
			return Promise.resolve();
		}

		filter_area.trigger_refresh = false;
		return filter_area
			.clear(false)
			.then(() => filter_area.set(filters || []))
			.then(() => {
				filter_area.trigger_refresh = true;
				lv.filters = filters || [];
				apply_columns();
				if (refresh) return lv.refresh(true);
			})
			.then(finish, finish);
	},

	/** Set Saved Layouts button text to the active layout name. */
	update_active_filter_label() {
		if (!this.layout_menu_group) return;

		const label = this.active_layout_label || this.default_layout_label;
		const label_node = $(
			`.inner-group-button[data-label="${encodeURIComponent(
				this.saved_layout_group_label
			)}"] button`
		)
			.contents()
			.first()[0];
		if (!label_node) return;
		label_node.textContent = label;
	},

	/** Show tick on the currently selected layout row. */
	update_active_filter_indicators() {
		const active_name = String(this.active_layout_name || "default_layout");
		this.get_layout_menu()
			.find(".saved-filter-item")
			.each((_, el) => {
				const $el = $(el);
				const is_active = String($el.attr("data-name")) === active_name;
				$el.find(".filter-check").toggleClass("invisible", !is_active);
			});
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

	/** Append Create / Manage action rows. */
	append_layout_action_items($menu) {
		const $create_item = this.layout_action_template(__("Create Layout"), "plus");
		$create_item.find(".dropdown-item").on("click", (e) => {
			e.preventDefault();
			this.open_layout_dialog();
		});
		$menu.append($create_item);
		const $manage_item = this.layout_action_template(__("Manage Layouts"), "settings");
		$manage_item.find(".dropdown-item").on("click", (e) => {
			e.preventDefault();
			this.open_manage_layouts_dialog();
		});
		$menu.append($manage_item);
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

	/** Build one static action menu row. */
	layout_action_template(label, icon) {
		return $(`
			<li class="saved-layout-action-item">
				<a class="dropdown-item d-flex align-items-center">
					<span class="mr-2 flex align-items-center">${frappe.utils.icon(icon)}</span>
					<span>${frappe.utils.escape_html(label)}</span>
				</a>
			</li>
		`);
	},

	/** Build one saved layout dropdown row. */
	filter_template(filter) {
		const is_active = filter.name === (this.active_layout_name || "default_layout");
		return $(`
			<li class="saved-filter-item" data-name="${filter.name}">
				<a class="dropdown-item d-flex justify-content-between align-items-center">
					<span class="d-flex align-items-center">
						<span class="filter-check mr-2 ${is_active ? "" : "invisible"}">
							${frappe.utils.icon("check", "xs")}
						</span>
						<span class="filter-label">
							${frappe.utils.escape_html(__(filter.filter_name))}
						</span>
					</span>
				</a>
			</li>
		`);
	},
};
