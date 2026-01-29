import Grid from "../grid";

frappe.ui.form.ControlTable = class ControlTable extends frappe.ui.form.Control {
	make() {
		super.make();

		// add title if prev field is not column / section heading or html
		this.grid = new Grid({
			frm: this.frm,
			df: this.df,
			parent: this.wrapper,
			control: this,
		});

		if (this.frm) {
			this.frm.grids[this.frm.grids.length] = this;
		}

		this.setup_paste_handler();
	}

	setup_paste_handler() {
		this.$wrapper.on("paste", ":text", (e) => {
			if ($(e.target).closest(".form-in-grid").length) {
				return;
			}

			const pasted_data = frappe.utils.get_clipboard_data(e);
			if (!pasted_data) {
				return;
			}

			const data = frappe.utils.csv_to_array(pasted_data, "\t");

			if (data.length === 1 && data[0].length === 1) {
				return;
			}

			e.preventDefault();
			this.handle_bulk_paste(e, data);
			return false;
		});
	}

	handle_bulk_paste(e, data) {
		if (!this.frm) {
			return;
		}

		const table_field = this.df.fieldname;
		const doctype = this.grid.doctype;
		const row_docname = $(e.target).closest(".grid-row").data("name");

		if (!row_docname || !locals[doctype]?.[row_docname]) {
			return;
		}

		const { fieldnames, fieldtypes } = this.get_paste_field_mapping(e, data, doctype);

		if (!fieldnames.length) {
			return;
		}

		if (this.get_field(data[0]?.[0])) {
			data.shift();
		}

		const row_idx = locals[doctype][row_docname].idx;
		const data_length = data.length;

		const pasted_rows = this.prepare_rows_for_paste(
			data,
			table_field,
			row_idx,
			fieldnames,
			fieldtypes
		);

		this.grid.refresh();
		this.frm.dirty();

		if (pasted_rows.length > 0) {
			this.apply_paste_values_serially(pasted_rows, doctype, data_length);
		}
	}

	get_paste_field_mapping(e, data, doctype) {
		const fieldnames = [];
		const fieldtypes = [];

		if (this.get_field(data[0]?.[0])) {
			data[0].forEach((column) => {
				const fieldname = this.get_field(column);
				fieldnames.push(fieldname);
				const df = frappe.meta.get_docfield(doctype, fieldname);
				fieldtypes.push(df?.fieldtype || "");
			});
		} else {
			const grid_rows = this.grid.grid_rows;
			if (!grid_rows?.length) {
				return { fieldnames, fieldtypes };
			}

			const visible_columns = grid_rows[0].get_visible_columns();
			const target_fieldname = $(e.target).data("fieldname");
			let target_column_matched = false;

			visible_columns.forEach((column) => {
				if (target_column_matched || column.fieldname === target_fieldname) {
					fieldnames.push(column.fieldname);
					const df = frappe.meta.get_docfield(doctype, column.fieldname);
					fieldtypes.push(df?.fieldtype || "");
					target_column_matched = true;
				}
			});
		}

		return { fieldnames, fieldtypes };
	}

	prepare_rows_for_paste(data, table_field, row_idx, fieldnames, fieldtypes) {
		const pasted_rows = [];
		const value_formatter_map = {
			Date: (val) => (val ? frappe.datetime.user_to_str(val) : val),
			Int: (val) => cint(val),
			Check: (val) => cint(val),
			Float: (val) => flt(val),
			Currency: (val) => flt(val),
		};

		data.forEach((row) => {
			if (!row.filter(Boolean).length) {
				return;
			}

			let row_doc;
			if (row_idx > this.frm.doc[table_field].length) {
				row_doc = frappe.model.add_child(this.frm.doc, this.grid.df.options, table_field);
			} else {
				row_doc = this.frm.doc[table_field][row_idx - 1];
			}

			if (!row_doc) {
				return;
			}

			const row_values = [];
			row.forEach((value, col_index) => {
				const fieldname = fieldnames[col_index];
				if (fieldname) {
					const fieldtype = fieldtypes[col_index];
					const formatter = value_formatter_map[fieldtype];
					const formatted_value = formatter ? formatter(value) : value;

					row_values.push({
						fieldname: fieldname,
						value: formatted_value,
					});
				}
			});

			pasted_rows.push({
				row_idx: row_idx - 1,
				values: row_values,
			});

			row_idx++;
		});

		return pasted_rows;
	}

	async apply_paste_values_serially(pasted_rows, doctype, data_length) {
		const table_field = this.df.fieldname;
		const show_progress = data_length >= 20;

		for (let i = 0; i < pasted_rows.length; i++) {
			const pasted_row = pasted_rows[i];
			const row_doc = this.frm.doc[table_field][pasted_row.row_idx];

			if (!row_doc) {
				continue;
			}
			await Promise.all(
				pasted_row.values.map((field_val) =>
					frappe.model.set_value(
						doctype,
						row_doc.name,
						field_val.fieldname,
						field_val.value
					)
				)
			);

			if (show_progress) {
				frappe.show_progress(
					__("Fetching details"),
					i + 1,
					pasted_rows.length,
					null,
					true
				);
			}
		}

		if (show_progress) {
			frappe.hide_progress();
		}
	}

	get_field(field_name) {
		if (!field_name) {
			return;
		}

		let fieldname;
		field_name = field_name.toLowerCase();

		this.grid?.meta?.fields.some((field) => {
			if (frappe.model.no_value_type.includes(field.fieldtype)) {
				return false;
			}

			const is_field_matching = () => {
				return (
					field.fieldname.toLowerCase() === field_name ||
					(field.label || "").toLowerCase() === field_name ||
					(__(field.label, null, field.parent) || "").toLowerCase() === field_name
				);
			};

			if (is_field_matching()) {
				fieldname = field.fieldname;
				return true;
			}
		});

		return fieldname;
	}

	refresh_input() {
		this.grid.refresh();
	}

	get_value() {
		if (this.grid) {
			return this.grid.get_data();
		}
	}

	set_input() {
		//
	}

	validate() {
		return this.get_value();
	}

	check_all_rows() {
		this.$wrapper.find(".grid-row-check")[0].click();
	}
};
