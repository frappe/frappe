frappe.provide("frappe.ui");

/** Drag-and-drop column picker (shared by layout create/edit). */
export default class LayoutFieldSelector {
	constructor({ parent, doctype, list_view, fields = null, preserved_widths = [] }) {
		this.parent = parent;
		this.doctype = doctype;
		this.list_view = list_view;
		this.meta = frappe.get_meta(doctype);
		this.max_number_of_fields = 50;
		this.subject_field = null;
		this.preserved_widths = preserved_widths || [];
		this.fields = this.normalize_fields(fields || this.get_default_fields()).uniqBy(
			(f) => f.fieldname
		);
		this.render();
	}

	normalize_fields(fields = []) {
		return fields.map(({ fieldname, label, type, width }) => {
			const field = { fieldname, label };
			if (type) field.type = type;
			if (width) field.width = width;
			return field;
		});
	}

	/** Default column width when none is saved on the layout. */
	get_default_column_width(fieldname, idx) {
		if (idx === 0) return 200;
		if (fieldname === "status_field") return 150;
		return 200;
	}

	get_field_width(field, idx) {
		if (cint(field.width)) return cint(field.width);

		const preserved = this.preserved_widths.find((col) => col.fieldname === field.fieldname);
		if (preserved?.width) return cint(preserved.width);

		const list_col = (this.list_view.columns || []).find(
			(col) =>
				col.df?.fieldname === field.fieldname ||
				(field.fieldname === "status_field" && col.type === "Status")
		);
		if (cint(list_col?.df?.width)) return cint(list_col.df.width);

		const max_width = this.list_view.column_max_widths?.[field.fieldname];
		if (cint(max_width)) return cint(max_width);

		const df = frappe.meta.get_docfield(this.doctype, field.fieldname);
		if (cint(df?.width)) return cint(df.width);

		return this.get_default_column_width(field.fieldname, idx);
	}

	get_default_fields() {
		const fields = [];
		this.set_subject_field(this.meta);
		fields.push({ ...this.subject_field });

		if (frappe.has_indicator(this.doctype)) {
			fields.push({
				type: "Status",
				label: __("Status"),
				fieldname: "status_field",
			});
		}

		(this.meta.fields || []).forEach((field) => {
			if (frappe.model.no_value_type.includes(field.fieldtype)) return;
			if (field.is_virtual) return;
			if (field.fieldname === this.subject_field.fieldname) return;
			if (field.fieldname === "status" && frappe.has_indicator(this.doctype)) return;
			if (!field.reqd && !field.in_list_view) return;

			fields.push({
				label: __(field.label, null, this.doctype),
				fieldname: field.fieldname,
			});
		});

		if (
			this.meta.title_field &&
			this.meta.title_field !== "name" &&
			fields.every((f) => f.fieldname !== "name")
		) {
			const has_name = (this.meta.fields || []).some(
				(f) => f.fieldname === "name" && (f.reqd || f.in_list_view)
			);
			if (has_name) {
				fields.push({ label: __("ID"), fieldname: "name" });
			}
		}

		return fields;
	}

	set_subject_field(meta) {
		this.subject_field = {
			label: __("ID"),
			fieldname: "name",
		};

		if (meta.title_field) {
			const field = frappe.meta.get_docfield(this.doctype, meta.title_field.trim());
			if (field) {
				this.subject_field = {
					label: __(field.label, null, this.doctype),
					fieldname: field.fieldname,
				};
			}
		}
	}

	set_status_field() {
		if (!frappe.has_indicator(this.doctype)) return;
		if (this.fields.some((f) => f.fieldname === "status_field")) return;
		this.fields.push({
			type: "Status",
			label: __("Status"),
			fieldname: "status_field",
		});
	}

	render() {
		let rows = ``;
		for (let idx in this.fields) {
			if (idx == this.max_number_of_fields) break;

			const field = this.fields[idx];
			const is_subject = idx == 0;
			const is_status = field.fieldname === "status_field";
			const is_sortable = is_subject ? "" : "sortable";
			const show_handle = is_subject ? "hide" : "";
			const can_remove = is_subject || is_status ? "hide" : "d-flex";
			const width = this.get_field_width(field, idx);

			rows += `
				<div class="control-input form-control fields_order ${is_sortable} flex"
					style="margin-bottom: 5px; padding-bottom: 1.5px;"
					data-fieldname="${field.fieldname}"
					data-label="${field.label}"
					data-type="${field.type || ""}">
					<div class="row flex-fill align-items-center">
						<div class="col-1 flex align-items-center justify-content-center px-1">
							${frappe.utils.icon("grip", "xs", "", "", "sortable-handle " + show_handle)}
						</div>
						<div class="col flex align-items-center px-0">
							${frappe.utils.escape_html(__(field.label, null, this.doctype))}
						</div>
						<div class="col-2">
							<input
								inputmode="numeric"
								autocomplete="off"
								class="form-control text-right layout-column-width"
								data-fieldname="${field.fieldname}"
								style="background-color: var(--modal-bg); height: 22px;"
								value="${width}"
							>
						</div>
						<div class="col-1 flex align-items-center justify-content-center px-0">
							<a class="text-muted remove-field align-items-center ${can_remove}"
								data-fieldname="${field.fieldname}">
								${frappe.utils.icon("x", "xs")}
							</a>
						</div>
					</div>
				</div>`;
		}

		this.parent.html(`
			<div class="form-group mb-0">
				<div class="text-right mb-1">
					<a class="add-new-fields text-muted" style="font-size: var(--text-xs); white-space: nowrap;">
						${__("+ Add / Remove Fields")}
					</a>
				</div>
				<div class="row flex-fill px-1 mb-1" style="font-size: var(--text-xs); color: var(--text-muted);">
					<div class="col-1"></div>
					<div class="col px-0">
						<label class="control-label mb-0" style="padding-right: 0; font-size: var(--text-xs);">${__(
							"Fields"
						)}</label>
					</div>
					<div class="col-2 text-right pr-2" style="white-space: nowrap;">
						${__("Width (px)")}
					</div>
					<div class="col-1"></div>
				</div>
				<div class="control-input-wrapper" style="max-height: 240px; overflow-y: auto;">
					${rows}
				</div>
			</div>
		`);

		const wrapper = this.parent.find(".control-input-wrapper").get(0);
		if (wrapper) {
			new Sortable(wrapper, {
				handle: ".sortable-handle",
				draggable: ".sortable",
				animation: 150,
				onUpdate: () => {
					this.sync_fields_from_dom();
					this.render();
				},
			});
		}

		this.parent.find(".add-new-fields").on("click", () => this.open_column_selector());
		this.parent.find(".remove-field").on("click", (e) => {
			e.preventDefault();
			this.remove_field($(e.currentTarget).data("fieldname"));
		});
	}

	sync_fields_from_dom() {
		const next_fields = [];
		this.parent.find(".fields_order").each((_, el) => {
			const $el = $(el);
			const fieldname = $el.data("fieldname");
			const field = {
				fieldname,
				label: $el.data("label"),
			};
			const type = $el.data("type");
			if (type) field.type = type;
			const width = cint(
				$el.find(`.layout-column-width[data-fieldname="${fieldname}"]`).val()
			);
			if (width) field.width = width;
			next_fields.push(field);
		});
		this.fields = next_fields;
	}

	remove_field(fieldname) {
		this.sync_fields_from_dom();
		this.fields = this.fields.filter((f) => f.fieldname !== fieldname);
		this.render();
	}

	open_column_selector() {
		this.sync_fields_from_dom();
		const selected = this.fields.map((f) => f.fieldname);

		const d = new frappe.ui.Dialog({
			title: __("{0} Fields", [__(this.doctype)]),
			size: "large",
			fields: [
				{
					label: __("Reset Fields"),
					fieldtype: "Button",
					fieldname: "reset_fields",
					click: () => this.reset_column_options(d),
				},
				{
					fieldtype: "Data",
					fieldname: "field_search",
					label: __("Search"),
					placeholder: __("Search by label or field name"),
				},
				{
					label: __("Select Fields (Up to {0})", [this.max_number_of_fields]),
					fieldtype: "MultiCheck",
					fieldname: "fields",
					options: this.get_doctype_field_options(selected),
					columns: 4,
				},
			],
		});

		d.set_primary_action(__("Save"), () => {
			const values = d.get_values().fields || [];

			this.fields = [];
			this.set_subject_field(this.meta);
			this.fields.push({ ...this.subject_field });
			this.set_status_field();

			for (const value of values) {
				if (this.fields.length >= this.max_number_of_fields) break;
				if (value === this.subject_field.fieldname) continue;
				if (value === "status_field") continue;

				const field = frappe.meta.get_docfield(this.doctype, value);
				if (field) {
					this.fields.push({
						label: __(field.label, null, this.doctype),
						fieldname: field.fieldname,
						width:
							cint(field.width) ||
							this.get_default_column_width(field.fieldname, this.fields.length),
					});
				}
			}

			this.fields = this.fields.uniqBy((f) => f.fieldname);
			this.render();
			d.hide();
		});

		d.show();
		this.setup_column_selector_search(d);
	}

	/** Filter MultiCheck rows as the user types in the search box. */
	setup_column_selector_search(dialog) {
		const search_field = dialog.get_field("field_search");
		if (!search_field?.$input) return;

		const filter_options = frappe.utils.debounce(() => {
			const query = (search_field.get_value() || "").toLowerCase().trim();
			const multicheck = dialog.get_field("fields");
			$(multicheck.wrapper)
				.find(".unit-checkbox")
				.each((_, el) => {
					const $el = $(el);
					const text = $el.find(".label-area").text().toLowerCase();
					const value = ($el.find(":checkbox").attr("data-unit") || "").toLowerCase();
					$el.toggle(!query || text.includes(query) || value.includes(query));
				});
		}, 200);

		search_field.$input.on("input", filter_options);
	}

	/** Whether a field can be picked for list columns (exclude meta-hidden and non-data fields). */
	is_selectable_layout_field(field) {
		if (frappe.model.no_value_type.includes(field.fieldtype)) return false;
		if (field.is_virtual) return false;
		if (cint(field.hidden)) return false;
		return true;
	}

	/** Disambiguate duplicate labels using fieldname. */
	get_field_picker_label(field, label_counts) {
		const label = __(field.label, null, this.doctype);
		if ((label_counts[label] || 0) > 1) {
			return `${label} (${field.fieldname})`;
		}
		return label;
	}

	reset_column_options(dialog) {
		frappe
			.xcall(
				"frappe.desk.doctype.list_view_settings.list_view_settings.get_default_listview_fields",
				{ doctype: this.doctype }
			)
			.then((fields) => {
				const field = dialog.get_field("fields");
				field.df.options = this.get_doctype_field_options(fields);
				dialog.refresh();
				this.setup_column_selector_search(dialog);
			});
	}

	get_doctype_field_options(selected_fieldnames = []) {
		const selected = new Set(selected_fieldnames);
		const candidates = [];

		(this.meta.fields || []).forEach((field) => {
			if (!this.is_selectable_layout_field(field)) return;
			candidates.push(field);
		});

		const label_counts = {};
		candidates.forEach((field) => {
			const label = __(field.label, null, this.doctype);
			label_counts[label] = (label_counts[label] || 0) + 1;
		});

		const options = candidates.map((field) => ({
			label: this.get_field_picker_label(field, label_counts),
			value: field.fieldname,
			checked: selected.has(field.fieldname),
			description: field.fieldname,
		}));

		if (frappe.has_indicator(this.doctype)) {
			options.unshift({
				label: __("Status"),
				value: "status_field",
				checked: selected.has("status_field"),
				description: "status_field",
			});
		}

		return options.uniqBy((option) => option.value);
	}

	get_columns() {
		this.sync_fields_from_dom();

		return this.fields.map((field, idx) => {
			const column = {
				fieldname: field.fieldname,
				label: __(field.label, null, this.doctype),
				width: cint(field.width) || this.get_default_column_width(field.fieldname, idx),
			};
			if (field.type) column.type = field.type;
			return column;
		});
	}
}
