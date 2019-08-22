import DataTable from 'frappe-datatable';
import get_custom_column_manager from './custom_column_manager';
import ColumnPickerFields from './column_picker_fields';

frappe.provide('frappe.data_import');

frappe.data_import.ImportPreview = class ImportPreview {
	constructor({ wrapper, doctype, preview_data, events = {} }) {
		frappe.import_preview = this;
		this.wrapper = wrapper;
		this.doctype = doctype;
		this.header_row = preview_data.header_row;
		this.preview_fields = preview_data.fields;
		this.preview_data = preview_data.data;
		this.preview_warnings = preview_data.warnings;
		this.events = events;

		frappe.model.with_doctype(doctype, () => {
			this.make_wrapper();
			this.prepare_columns();
			this.prepare_data();
			this.render_warnings(this.preview_warnings);
			this.render_datatable();
		});
	}

	make_wrapper() {
		this.wrapper.html(`
			<div>
				<div class="warnings"></div>
				<div class="table-preview"></div>
				<div class="table-actions margin-top">
					<button class="btn btn-xs btn-default" data-action="add_row">
						${__('Add Row')}
					</button>
				</div>
			</div>
		`);
		frappe.utils.bind_actions_with_class(this.wrapper, this);

		this.$warnings = this.wrapper.find('.warnings');
		this.$table_preview = this.wrapper.find('.table-preview');
	}

	prepare_columns() {
		this.columns = this.preview_fields.map((df, i) => {
			let header_row_index = i - 1;
			if (df.skip_import) {
				return {
					id: frappe.utils.get_random(6),
					name: df.label,
					skip_import: true,
					editable: false,
					focusable: false,
					header_row_index,
					format: (value, row, column, data) => {
						return `<div class="text-muted">${value}</div>`;
					}
				};
			}

			let column_title = df.label;
			if (this.doctype !== df.parent) {
				column_title = `${df.label} (${df.parent})`;
			}
			let meta = frappe.get_meta(this.doctype);
			if (meta.autoname === `field:${df.fieldname}`) {
				column_title = `ID (${df.label})`;
			}
			return {
				id: df.fieldname,
				name: column_title,
				df: df,
				editable: true,
				align: 'left',
				header_row_index
			};
		});
	}

	prepare_data() {
		this.preview_data = this.preview_data.map(row => {
			return row.map(cell => {
				if (cell == null) {
					return '';
				}
				return cell;
			});
		});
	}

	render_warnings(warnings) {
		let warning_html = warnings
			.map(warning => {
				return `<div style="line-height: 2">${warning}</div>`;
			})
			.join('');

		let html = `<div class="border text-muted padding rounded margin-bottom">${warning_html}</div>`;
		this.$warnings.html(html);
	}

	render_datatable() {
		let self = this;

		this.datatable = new DataTable(this.$table_preview.get(0), {
			data: this.preview_data,
			columns: this.columns,
			layout: 'fixed',
			cellHeight: 35,
			serialNoColumn: false,
			checkboxColumn: false,
			pasteFromClipboard: true,
			headerDropdown: [
				{
					label: __('Remap Column'),
					action: col => this.remap_column(col)
				},
				{
					label: __('Skip Import'),
					action: col => this.skip_import(col)
				}
			],
			overrideComponents: {
				ColumnManager: get_custom_column_manager(this.header_row)
			}
		});

		this.datatable.style.setStyle('.dt-dropdown__list-item:nth-child(-n+4)', {
			display: 'none'
		});

		this.add_color_to_column_header();
	}

	get_rows_as_csv_array() {
		return this.datatable.getRows().map(row => {
			return row.map(cell => cell.content);
		});
	}

	add_color_to_column_header() {
		let columns = this.datatable.getColumns();
		columns.forEach(col => {
			if (!col.skip_import && col.df) {
				this.datatable.style.setStyle(
					`.dt-header .dt-cell--col-${col.colIndex}, .dt-header .dt-cell--col-${col.colIndex} .dt-dropdown__toggle`,
					{
						backgroundColor: frappe.ui.color.get_color_shade(
							'green',
							'extra-light'
						),
						color: frappe.ui.color.get_color_shade('green', 'dark')
					}
				);
			}
			if (col.skip_import && col.name !== 'Sr. No') {
				this.datatable.style.setStyle(
					`.dt-header .dt-cell--col-${col.colIndex}, .dt-header .dt-cell--col-${col.colIndex} .dt-dropdown__toggle`,
					{
						backgroundColor: frappe.ui.color.get_color_shade(
							'orange',
							'extra-light'
						),
						color: frappe.ui.color.get_color_shade('orange', 'dark')
					}
				);
				this.datatable.style.setStyle(`.dt-cell--col-${col.colIndex}`, {
					backgroundColor: frappe.ui.color.get_color_shade('white', 'light')
				});
			}
		});
	}

	add_row() {
		this.preview_data.push([]);
		this.datatable.refresh(this.preview_data);
	}

	remap_column(col) {
		let column_picker_fields = new ColumnPickerFields({
			doctype: this.doctype
		});
		let dialog = new frappe.ui.Dialog({
			title: __('Remap Column: {0}', [col.name]),
			fields: [
				{
					fieldtype: 'Autocomplete',
					fieldname: 'fieldname',
					label: __('Select field'),
					max_items: Infinity,
					options: column_picker_fields.get_fields_as_options()
				}
			],
			primary_action: ({ fieldname }) => {
				if (!fieldname) return;
				this.events.remap_column(col.header_row_index, fieldname);
				dialog.hide();
			}
		});
		dialog.show();
	}

	skip_import(col) {
		this.events.skip_import(col.header_row_index);
	}
};
