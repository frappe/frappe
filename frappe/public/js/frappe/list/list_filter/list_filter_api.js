/** Server fetch helpers for saved list layouts. */
export const ListFilterAPI = {
	/** Fetch global and user-specific layouts for the current doctype. */
	get_list_filters() {
		if (frappe.session.user === "Guest") return Promise.resolve();
		return frappe.db
			.get_list("List Filter", {
				fields: [
					"name",
					"filter_name",
					"for_user",
					"filters",
					"columns",
					"sort_field",
					"sort_order",
					"route_signature",
				],
				filters: { reference_doctype: this.list_view.doctype },
				or_filters: [
					["for_user", "=", frappe.session.user],
					["for_user", "=", ""],
				],
				order_by: "filter_name asc",
				limit: 200,
			})
			.then((filters) => {
				this.filters = (filters || []).map((layout) => this.normalize_layout(layout));
			});
	},

	/** Cache parsed layout fields to avoid repeated JSON.parse on hot paths. */
	normalize_layout(layout) {
		if (!layout || layout._normalized) return layout;

		layout._parsed_filters = this.parse_layout_filters(layout);
		layout._parsed_columns = this._parse_layout_columns(layout);
		if (layout.route_signature !== undefined && layout.route_signature !== null) {
			layout._route_signature = layout.route_signature;
		} else {
			layout._route_signature = this.get_route_signature_from_filters(
				layout._parsed_filters
			);
		}
		layout._normalized = true;
		return layout;
	},

	/** Return selected layout document by name. */
	get_active_layout() {
		if (!this.active_layout_name || this.active_layout_name === "default_layout") return null;
		return (
			(this.filters || []).find((filter) => filter.name === this.active_layout_name) || null
		);
	},

	/** Parse saved layout columns safely. */
	get_layout_columns(layout) {
		if (!layout) return [];
		if (layout._parsed_columns) return layout._parsed_columns;
		return this._parse_layout_columns(layout);
	},

	_parse_layout_columns(layout) {
		try {
			const columns = JSON.parse(layout?.columns || "[]");
			return Array.isArray(columns) ? columns : [];
		} catch {
			return [];
		}
	},

	/** Whether current user can update this layout record. */
	can_edit_layout(layout) {
		if (!layout) return false;
		if (!layout.for_user) {
			return frappe.user.has_role(["System Manager", "Administrator"]);
		}
		return layout.for_user === frappe.session.user;
	},

	/** Insert a new saved layout from the layout dialog. */
	create_layout_from_dialog({
		filter_name,
		is_global,
		filters,
		columns,
		sort_field,
		sort_order,
		route_signature,
	}) {
		return frappe.db
			.insert({
				doctype: "List Filter",
				reference_doctype: this.list_view.doctype,
				filter_name,
				for_user: is_global ? "" : frappe.session.user,
				filters: JSON.stringify(filters || []),
				columns: JSON.stringify(columns || []),
				sort_field,
				sort_order,
				route_signature: route_signature || "",
			})
			.then((doc) => {
				this.filters = [...(this.filters || []), this.normalize_layout(doc)];
				return doc;
			});
	},

	/** Update an existing layout from the layout dialog. */
	update_layout_from_dialog(
		layout,
		{ filter_name, is_global, filters, columns, sort_field, sort_order, route_signature }
	) {
		if (!layout?.name || !this.can_edit_layout(layout)) {
			return Promise.resolve();
		}
		const args = {
			name: layout.name,
			filter_name,
			filters: JSON.stringify(filters || []),
			columns: JSON.stringify(columns || []),
			sort_field,
			sort_order,
			route_signature: route_signature || "",
		};
		if (this.can_add_global && is_global !== undefined) {
			args.for_user = is_global ? "" : frappe.session.user;
		}
		return frappe
			.call({
				method: "frappe.desk.doctype.list_filter.list_filter.update_list_filter",
				args,
			})
			.then((r) => {
				const updated = r.message;
				if (!updated) return updated;
				const index = (this.filters || []).findIndex((row) => row.name === updated.name);
				if (index >= 0) {
					this.filters[index] = this.normalize_layout({
						...this.filters[index],
						...updated,
					});
				}
				return updated;
			});
	},

	/** Whether current user can create or edit global layouts. */
	get can_add_global() {
		return frappe.user.has_role(["System Manager", "Administrator"]);
	},

	/** Delete a saved layout the current user is allowed to modify. */
	delete_layout(layout) {
		if (!layout?.name || !this.can_edit_layout(layout)) {
			return Promise.resolve();
		}

		return frappe
			.call({
				method: "frappe.desk.doctype.list_filter.list_filter.delete_list_filter",
				args: { name: layout.name },
			})
			.then(() => {
				this.filters = (this.filters || []).filter((row) => row.name !== layout.name);
				if (this.active_layout_name === layout.name) {
					this.active_layout_name = "default_layout";
					this.active_layout_label = this.default_layout_label;
					return this.apply_default_layout();
				}
			});
	},

	/** Persist layout columns and route signature only (debounced during column resize). */
	update_layout_columns(layout, columns, { debounce = true } = {}) {
		if (!layout?.name || !this.can_edit_layout(layout)) return Promise.resolve();

		if (debounce) {
			if (!this._debounced_save_layout_columns) {
				this._debounced_save_layout_columns = frappe.utils.debounce(
					(layout, columns) => this._save_layout_columns(layout, columns),
					500
				);
			}
			this._debounced_save_layout_columns(layout, columns);
			return Promise.resolve();
		}

		return this._save_layout_columns(layout, columns);
	},

	_save_layout_columns(layout, columns) {
		const columns_json = JSON.stringify(columns || []);
		return frappe
			.call({
				method: "frappe.desk.doctype.list_filter.list_filter.update_list_filter",
				args: {
					name: layout.name,
					columns: columns_json,
				},
			})
			.then((r) => {
				const updated = r.message;
				if (!updated) return updated;

				const index = (this.filters || []).findIndex((row) => row.name === layout.name);
				if (index >= 0) {
					this.filters[index] = this.normalize_layout({
						...this.filters[index],
						...updated,
						columns: columns_json,
						_parsed_columns: columns,
					});
				}
				return updated;
			});
	},
};
