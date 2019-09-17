import DataTable from 'frappe-datatable';
import get_custom_column_manager from './custom_column_manager';
import ColumnPickerFields from './column_picker_fields';

frappe.provide('frappe.data_import');

const SVG_ICONS = {
	'checkbox-circle-line': `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="import-success">
		<g>
			<path fill="none" d="M0 0h24v24H0z"/>
			<path d="M12 22C6.477 22 2 17.523 2 12S6.477 2 12 2s10 4.477 10 10-4.477 10-10 10zm0-2a8 8 0 1 0 0-16 8 8 0 0 0 0 16zm-.997-4L6.76 11.757l1.414-1.414 2.829 2.829 5.656-5.657 1.415 1.414L11.003 16z"/>
		</g>
	</svg>`
};

frappe.data_import.ImportPreview = class ImportPreview {
	constructor({ wrapper, doctype, preview_data, import_log, warnings, events = {} }) {
		frappe.import_preview = this;
		this.wrapper = wrapper;
		this.doctype = doctype;
		this.preview_data = preview_data;
		this.events = events;
		this.warnings = warnings;
		this.import_log = import_log;

		frappe.model.with_doctype(doctype, () => {
			this.refresh();
		});
	}

	refresh() {
		this.header_row = this.preview_data.header_row;
		this.fields = this.preview_data.fields;
		this.data = this.preview_data.data;
		this.max_rows_exceeded = this.preview_data.max_rows_exceeded;
		this.make_wrapper();
		this.prepare_columns();
		this.prepare_data();
		this.render_warnings(this.warnings);
		this.render_datatable();
		this.setup_styles();
		this.add_actions();
	}

	make_wrapper() {
		this.wrapper.html(`
			<div>
				<div class="warnings text-muted"></div>
				<div class="table-preview"></div>
				<div class="table-actions margin-top"></div>
			</div>
		`);
		frappe.utils.bind_actions_with_class(this.wrapper, this);

		this.$warnings = this.wrapper.find('.warnings');
		this.$table_preview = this.wrapper.find('.table-preview');
	}

	prepare_columns() {
		let column_width = 120;
		this.columns = this.fields.map((df, i) => {
			let header_row_index = i - 1;
			if (df.skip_import) {
				return {
					id: frappe.utils.get_random(6),
					name: df.label,
					skip_import: true,
					editable: false,
					focusable: false,
					align: 'left',
					header_row_index,
					width: df.label === 'Sr. No' ? 60 : column_width,
					format: (value, row, column, data) => {
						let html = `<div class="text-muted">${value}</div>`;
						if (df.label === 'Sr. No' && this.is_row_imported(row)) {
							html = `
								<div class="flex justify-between">${SVG_ICONS['checkbox-circle-line'] +
									html}</div>
							`;
						}
						return html;
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
				header_row_index,
				width: column_width
			};
		});
	}

	prepare_data() {
		this.data = this.data.map(row => {
			return row.map(cell => {
				if (cell == null) {
					return '';
				}
				return cell;
			});
		});
	}

	render_warnings(warnings) {
		let html = '';
		if (warnings.length > 0) {
			let warning_html = warnings
				.map(warning => {
					return `<li>${warning}</li>`;
				})
				.join('');

			html = `<ul>${warning_html}</ul>`;
		}
		this.$warnings.html(html);
	}

	render_datatable() {
		if (this.datatable) {
			this.datatable.destroy();
		}

		let no_data_message = this.max_rows_exceeded
			? __('Cannot load preview for more than 500 rows. You can still remap or skip columns.')
			: __('No Data');
		no_data_message = `<span class="text-muted">${no_data_message}</span>`;

		this.datatable = new DataTable(this.$table_preview.get(0), {
			data: this.data,
			columns: this.columns,
			layout: 'fixed',
			cellHeight: 35,
			serialNoColumn: false,
			checkboxColumn: false,
			pasteFromClipboard: true,
			noDataMessage: no_data_message,
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

		if (this.data.length === 0) {
			this.datatable.style.setStyle('.dt-scrollable', {
				height: 'auto'
			});
		}

		this.datatable.style.setStyle('.dt-dropdown__list-item:nth-child(-n+4)', {
			display: 'none'
		});
	}

	get_rows_as_csv_array() {
		return this.datatable.getRows().map(row => {
			return row.map(cell => cell.content);
		});
	}

	setup_styles() {
		let columns = this.datatable.getColumns();
		columns.forEach(col => {
			let class_name = [
				`.dt-header .dt-cell--col-${col.colIndex}`,
				`.dt-header .dt-cell--col-${col.colIndex} .dt-dropdown__toggle`
			].join(',');

			if (!col.skip_import && col.df) {
				this.datatable.style.setStyle(class_name, {
					backgroundColor: frappe.ui.color.get_color_shade(
						'green',
						'extra-light'
					),
					color: frappe.ui.color.get_color_shade('green', 'dark')
				});
			}
			if (col.skip_import && col.name !== 'Sr. No') {
				this.datatable.style.setStyle(class_name, {
					backgroundColor: frappe.ui.color.get_color_shade(
						'orange',
						'extra-light'
					),
					color: frappe.ui.color.get_color_shade('orange', 'dark')
				});
				this.datatable.style.setStyle(`.dt-cell--col-${col.colIndex}`, {
					backgroundColor: frappe.ui.color.get_color_shade('white', 'light')
				});
			}
		});
		// import success checkbox
		this.datatable.style.setStyle(`svg.import-success`, {
			width: '16px',
			fill: frappe.ui.color.get_color_shade('green', 'dark')
		});
		// make successfully imported rows readonly
		let row_classes = this.datatable
			.getRows()
			.filter(row => this.is_row_imported(row))
			.map(row => row.meta.rowIndex)
			.map(i => `.dt-row-${i} .dt-cell`)
			.join(',');
		this.datatable.style.setStyle(row_classes, {
			pointerEvents: 'none',
			backgroundColor: frappe.ui.color.get_color_shade('white', 'light'),
			color: frappe.ui.color.get_color_shade('black', 'extra-light'),
		});
	}

	add_actions() {
		let failures = this.import_log.filter(log => !log.success);
		if (failures.length > 0) {
			this.wrapper.find('.table-actions').append(
				`<button class="btn btn-xs btn-default" data-action="export_errored_rows">
					${__('Export rows which are not imported')}
				</button>
			`);
		}
	}

	export_errored_rows() {
		this.events.export_errored_rows();
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

	is_row_imported(row) {
		let serial_no = row[0].content;
		return this.import_log.find(log => {
			return log.success && log.row_indexes.includes(serial_no);
		});
	}
};
