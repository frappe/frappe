import LayoutFieldSelector from "./layout_field_selector";

frappe.provide("frappe.ui");

/** Create or edit a saved list layout (name, filters, sort, columns). */
export default class LayoutDialog {
	constructor({ list_view, layout = null, duplicate_from = null, on_save }) {
		this.list_view = list_view;
		this.doctype = list_view.doctype;
		this.layout = duplicate_from ? null : layout;
		this.duplicate_from = duplicate_from;
		this.source_layout = duplicate_from || layout;
		this.on_save = on_save;
		this.can_add_global = frappe.user.has_role(["System Manager", "Administrator"]);

		frappe.model.with_doctype(this.doctype, () => this.make_dialog());
	}

	make_dialog() {
		const is_edit = Boolean(this.layout);
		const fields = [
			{
				fieldname: "filter_name",
				fieldtype: "Data",
				label: __("Layout Name"),
				reqd: 1,
				default: is_edit ? this.layout.filter_name : "",
			},
		];

		if (this.can_add_global) {
			fields.push({ fieldtype: "Column Break" });
			fields.push({
				fieldname: "is_global",
				fieldtype: "Check",
				label: __("Available to All Users"),
				description: __("Make this layout visible for everyone."),
				default: this.get_initial_is_global(),
			});
		}

		fields.push(
			{
				fieldtype: "Section Break",
				label: __("Filters"),
				description: __("Define which records should appear in this list."),
			},
			{ fieldtype: "HTML", fieldname: "filter_area" },
			{
				fieldtype: "Section Break",
				label: __("Sort By"),
				description: __("Choose the default order in which records appear."),
			},
			{ fieldtype: "HTML", fieldname: "sort_area" },
			{
				fieldtype: "Section Break",
				label: __("Columns"),
				description: __("Choose and order the columns to display."),
			},
			{ fieldtype: "HTML", fieldname: "columns_area" }
		);

		this.dialog = new frappe.ui.Dialog({
			title: is_edit ? __("Edit Layout") : __("Create Layout"),
			size: "large",
			fields,
			primary_action_label: is_edit ? __("Update") : __("Create"),
			primary_action: () => this.save_layout(),
		});

		this.make_filter_area(this.dialog.get_field("filter_area").$wrapper);
		this.make_sort_selector(this.dialog.get_field("sort_area").$wrapper);
		this.preserved_layout_columns = [];
		this.field_selector = new LayoutFieldSelector({
			parent: this.dialog.get_field("columns_area").$wrapper,
			doctype: this.doctype,
			list_view: this.list_view,
			fields: this.get_initial_columns(),
			preserved_widths: this.preserved_layout_columns,
		});
		this.dialog.show();
	}

	get_initial_is_global() {
		if (!this.source_layout) return 0;
		return this.source_layout.for_user ? 0 : 1;
	}

	get_initial_columns() {
		if (this.source_layout?.columns) {
			try {
				const columns = JSON.parse(this.source_layout.columns || "[]");
				if (Array.isArray(columns) && columns.length) {
					this.preserved_layout_columns = columns;
					return columns.map(({ fieldname, label, type, width }) => ({
						fieldname,
						label,
						...(type ? { type } : {}),
						...(width ? { width } : {}),
					}));
				}
			} catch {
				// fall through to defaults
			}
		}

		return null;
	}

	make_filter_area(parent) {
		this.filter_group = new frappe.ui.FilterGroup({
			parent,
			doctype: this.doctype,
			on_change: () => this.sync_filter_empty_state(),
		});

		const filters = this.get_initial_filters();
		if (filters.length) {
			this.filter_group.toggle_empty_filters(false);
			this.filter_group.add_filters(filters).then(() => {
				this.filter_group.toggle_empty_filters(false);
				this.sync_filter_empty_state();
			});
		}
	}

	/** Hide "No filters selected" when filters are present (FilterGroup only toggles on user actions). */
	sync_filter_empty_state() {
		const has_filters =
			this.filter_group.get_filters().length > 0 ||
			this.filter_group.filters.some((f) => f.wrapper?.is(":visible") && f.field);
		this.filter_group.toggle_empty_filters(!has_filters);
	}

	make_sort_selector(parent) {
		const sorting = this.get_initial_sorting();
		this.sort_selector = new frappe.ui.SortSelector({
			parent,
			doctype: this.doctype,
			args: {
				sort_by: sorting.sort_by,
				sort_order: sorting.sort_order,
			},
			onchange: () => {},
		});
	}

	get_initial_sorting() {
		if (this.source_layout?.sort_field) {
			return {
				sort_by: this.source_layout.sort_field,
				sort_order: this.source_layout.sort_order || "desc",
			};
		}
		return {
			sort_by: this.list_view.sort_by || this.list_view.meta?.sort_field || "creation",
			sort_order: this.list_view.sort_order || this.list_view.meta?.sort_order || "desc",
		};
	}

	get_sorting() {
		return {
			sort_field: this.sort_selector?.sort_by || this.get_initial_sorting().sort_by,
			sort_order: this.sort_selector?.sort_order || this.get_initial_sorting().sort_order,
		};
	}

	get_initial_filters() {
		if (this.source_layout?.filters) {
			try {
				const filters = JSON.parse(this.source_layout.filters || "[]");
				return Array.isArray(filters) ? filters : [];
			} catch {
				return [];
			}
		}
		return (this.list_view.filter_area?.get() || []).map((filter) => filter.slice(0, 4));
	}

	get_filters() {
		return this.filter_group.get_filters().map((filter) => filter.slice(0, 4));
	}

	get_form_values() {
		return {
			filter_name: this.dialog.get_value("filter_name")?.trim(),
			is_global: this.can_add_global ? this.dialog.get_value("is_global") : false,
		};
	}

	filter_name_exists(filter_name) {
		return (this.list_view.list_filter?.filters || []).some(
			(row) =>
				row.filter_name === filter_name && (!this.layout || row.name !== this.layout.name)
		);
	}

	save_layout() {
		const { filter_name, is_global } = this.get_form_values();
		if (!filter_name) {
			frappe.msgprint(__("Layout Name is required"));
			return;
		}

		if (this.filter_name_exists(filter_name)) {
			frappe.msgprint(__("A layout with this name already exists"));
			return;
		}

		const columns = this.field_selector.get_columns();
		if (!columns.length) {
			frappe.msgprint(__("Select at least one field"));
			return;
		}

		const sorting = this.get_sorting();
		const filters = this.get_filters();
		const payload = {
			filter_name,
			is_global,
			filters,
			columns,
			sort_field: sorting.sort_field,
			sort_order: sorting.sort_order,
			route_signature:
				this.list_view.list_filter?.get_route_signature_from_filters?.(filters) || "",
		};

		const save_promise = this.layout
			? this.list_view.list_filter.update_layout_from_dialog(this.layout, payload)
			: this.list_view.list_filter.create_layout_from_dialog(payload);

		return save_promise.then(() => {
			const esc_name = frappe.utils.escape_html(filter_name);
			const message = this.layout
				? __("Layout <b>{0}</b> updated", [esc_name])
				: __("Layout <b>{0}</b> created", [esc_name]);
			frappe.show_alert({ message, indicator: "green" });
			this.dialog.hide();
			this.on_save?.();
		});
	}
}
