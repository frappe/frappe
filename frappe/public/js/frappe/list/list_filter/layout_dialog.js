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
				label: __("Layout name"),
				reqd: 1,
				default: is_edit ? this.layout.filter_name : "",
			},
		];

		if (this.can_add_global) {
			fields.push({
				fieldname: "is_global",
				fieldtype: "Check",
				label: __("Available to all users"),
				default: this.get_initial_is_global(),
			});
		}

		const sorting = this.get_initial_sorting();

		fields.push(
			{
				fieldtype: "Section Break",
				label: __("Filters & Sorting"),
				fieldname: "filters_sort_sb",
			},
			{ fieldtype: "HTML", fieldname: "filter_area" },
			{ fieldtype: "Section Break", fieldname: "sort_row_sb", hide_border: true },
			{
				fieldname: "sort_field",
				fieldtype: "Autocomplete",
				label: __("Sort Field"),
				options: this.get_sort_field_options(),
				default: sorting.sort_by,
				reqd: 1,
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "sort_order",
				fieldtype: "Select",
				label: __("Sort Order"),
				options: [
					{ label: __("Descending"), value: "desc" },
					{ label: __("Ascending"), value: "asc" },
				],
				default: sorting.sort_order,
				reqd: 1,
			},
			{ fieldtype: "Section Break", label: __("Columns") },
			{ fieldtype: "HTML", fieldname: "columns_area" }
		);

		this.dialog = new frappe.ui.Dialog({
			title: is_edit ? __("Edit layout") : __("Create layout"),
			size: "large",
			fields,
			primary_action_label: is_edit ? __("Update") : __("Create"),
			primary_action: () => this.save_layout(),
		});

		this.make_filter_area(this.dialog.get_field("filter_area").$wrapper);
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

	/** Hide "No filters selected" when any filter row is present (incomplete rows count too). */
	sync_filter_empty_state() {
		const has_filters = this.filter_group.wrapper.find(".filter-box").length > 0;
		this.filter_group.toggle_empty_filters(!has_filters);
	}

	/** Sortable field options for the sort-by Autocomplete (matches list SortSelector). */
	get_sort_field_options() {
		const meta = frappe.get_meta(this.doctype);
		let options = [
			{ fieldname: "modified" },
			{ fieldname: "name" },
			{ fieldname: "creation" },
			{ fieldname: "idx" },
		];

		if (meta?.title_field) {
			options.splice(1, 0, { fieldname: meta.title_field });
		}
		if (meta?.sort_field) {
			const sort_field = meta.sort_field.split(",")[0].split(" ")[0];
			options.splice(1, 0, { fieldname: sort_field });
		}

		(meta?.fields || []).forEach((df) => {
			if (
				(df.mandatory || df.bold || df.in_list_view || df.reqd) &&
				frappe.model.is_value_type(df.fieldtype) &&
				frappe.perm.has_perm(this.doctype, df.permlevel, "read")
			) {
				options.push({ fieldname: df.fieldname, label: df.label });
			}
		});

		return options
			.uniqBy((o) => o.fieldname)
			.map((o) => ({
				value: o.fieldname,
				label: o.label || this.get_sort_field_label(o.fieldname),
			}));
	}

	get_sort_field_label(fieldname) {
		if (fieldname === "idx") {
			return __("Most Used");
		}
		return frappe.meta.get_label(this.doctype, fieldname);
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
		const initial = this.get_initial_sorting();
		return {
			sort_field: this.dialog.get_value("sort_field") || initial.sort_by,
			sort_order: this.dialog.get_value("sort_order") || initial.sort_order,
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
			frappe.msgprint(__("Layout name is required"));
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
