import DataTable from 'frappe-datatable';
import { get_columns_for_picker } from './data_exporter';

frappe.provide('frappe.data_import');

frappe.data_import.ImportPreview = class ImportPreview {
	constructor({
		wrapper,
		doctype,
		preview_data,
		frm,
		import_log,
		events = {}
	}) {
		this.wrapper = wrapper;
		this.doctype = doctype;
		this.preview_data = preview_data;
		this.events = events;
		this.import_log = import_log;
		this.frm = frm;

		frappe.model.with_doctype(doctype, () => {
			this.refresh();
		});
	}

	refresh() {
		this.data = this.preview_data.data;
		this.make_wrapper();
		this.prepare_columns();
		this.prepare_data();
		this.render_datatable();
		this.setup_styles();
		this.add_actions();
	}

	make_wrapper() {
		this.wrapper.html(`
			<div>
				<div class="row">
					<div class="col-sm-12">
						<div class="table-actions margin-bottom">
						</div>
						<div class="table-preview border"></div>
						<div class="table-message"></div>
					</div>
				</div>
			</div>
		`);
		frappe.utils.bind_actions_with_object(this.wrapper, this);

		this.$table_preview = this.wrapper.find('.table-preview');
	}

	prepare_columns() {
		this.columns = this.preview_data.columns.map((col, i) => {
			let df = col.df;
			let column_width = 120;
			if (col.header_title === 'Sr. No') {
				return {
					id: 'srno',
					name: 'Sr. No',
					content: 'Sr. No',
					editable: false,
					focusable: false,
					align: 'left',
					width: 60
				};
			}

			if (col.skip_import) {
				let show_warnings_button = `<button class="btn btn-xs" data-action="show_column_warning" data-col="${i}">
					<i class="octicon octicon-stop"></i></button>`;
				if (!col.df) {
					// increase column width for unidentified columns
					column_width += 50;
				}
				let column_title = `<span class="indicator red">
					${col.header_title || `<i>${__('Untitled Column')}</i>`}
					${!col.df ? show_warnings_button : ''}
				</span>`;
				return {
					id: frappe.utils.get_random(6),
					name: col.header_title || (df ? df.label : 'Untitled Column'),
					content: column_title,
					skip_import: true,
					editable: false,
					focusable: false,
					align: 'left',
					width: column_width,
					format: value => `<div class="text-muted">${value}</div>`
				};
			}

			let date_format = col.date_format
				? col.date_format
					.replace('%Y', 'yyyy')
					.replace('%y', 'yy')
					.replace('%m', 'mm')
					.replace('%d', 'dd')
				: null;

			let column_title = `<span class="indicator green">
				${col.header_title || df.label}
				${date_format ? `(${date_format})` : ''}
			</span>`;

			return {
				id: df.fieldname,
				name: col.header_title,
				content: column_title,
				df: df,
				editable: false,
				align: 'left',
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

	render_datatable() {
		if (this.datatable) {
			this.datatable.destroy();
		}

		this.datatable = new DataTable(this.$table_preview.get(0), {
			data: this.data,
			columns: this.columns,
			layout: this.columns.length < 10 ? 'fluid' : 'fixed',
			cellHeight: 35,
			serialNoColumn: false,
			checkboxColumn: false,
			noDataMessage: __('No Data'),
			disableReorderColumn: true
		});

		let {
			max_rows_exceeded,
			max_rows_in_preview,
			total_number_of_rows
		} = this.preview_data;
		if (max_rows_exceeded) {
			let parts = [max_rows_in_preview, total_number_of_rows];
			this.wrapper.find('.table-message').html(`
				<div class="text-muted margin-top text-medium">
				${__('Showing only first {0} rows out of {1}', parts)}
				</div>
			`);
		}

		if (this.data.length === 0) {
			this.datatable.style.setStyle('.dt-scrollable', {
				height: 'auto'
			});
		}

		this.datatable.style.setStyle('.dt-dropdown', {
			display: 'none'
		});
	}

	setup_styles() {
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
			color: frappe.ui.color.get_color_shade('black', 'extra-light')
		});
	}

	add_actions() {
		let actions = [
			{
				label: __('Map Columns'),
				handler: 'show_column_mapper',
				condition: this.frm.doc.status !== 'Success'
			},
			{
				label: __('Export Errored Rows'),
				handler: 'export_errored_rows',
				condition: this.import_log.filter(log => !log.success).length > 0
			},
			{
				label: __('Show Warnings'),
				handler: 'show_warnings',
				condition: this.preview_data.warnings.length > 0
			}
		];

		let html = actions
			.filter(action => action.condition)
			.map(action => {
				return `<button class="btn btn-sm btn-default" data-action="${action.handler}">
					${action.label}
				</button>
			`;
			});

		this.wrapper.find('.table-actions').html(html);
	}

	export_errored_rows() {
		this.frm.trigger('export_errored_rows');
	}

	show_warnings() {
		this.frm.scroll_to_field('import_warnings');
	}

	show_column_warning(_, $target) {
		let $warning = this.frm
			.get_field('import_warnings')
			.$wrapper.find(`[data-col=${$target.data('col')}]`);
		frappe.utils.scroll_to($warning, true, 30);
	}

	show_column_mapper() {
		let column_picker_fields = get_columns_for_picker(this.doctype);
		let changed = [];
		let fields = this.preview_data.columns.map((col, i) => {
			let df = col.df;
			if (col.header_title === 'Sr. No') return [];

			let fieldname;
			if (!df) {
				fieldname = null;
			} else if (col.map_to_field) {
				fieldname = col.map_to_field;
			} else if (col.is_child_table_field) {
				fieldname = `${col.child_table_df.fieldname}.${df.fieldname}`;
			} else {
				fieldname = df.fieldname;
			}
			return [
				{
					label: '',
					fieldtype: 'Data',
					default: col.header_title,
					fieldname: `Column ${i}`,
					read_only: 1
				},
				{
					fieldtype: 'Column Break'
				},
				{
					fieldtype: 'Autocomplete',
					fieldname: i,
					label: '',
					max_items: Infinity,
					options: [
						{
							label: __("Don't Import"),
							value: "Don't Import"
						}
					].concat(get_fields_as_options(this.doctype, column_picker_fields)),
					default: fieldname || "Don't Import",
					change() {
						changed.push(i);
					}
				},
				{
					fieldtype: 'Section Break'
				}
			];
		});
		// flatten the array
		fields = fields.reduce((acc, curr) => [...acc, ...curr]);
		let file_name = (this.frm.doc.import_file || '').split('/').pop();
		let parts = [file_name.bold(), this.doctype.bold()];
		fields = [
			{
				fieldtype: 'HTML',
				fieldname: 'heading',
				options: `
					<div class="margin-top text-muted">
					${__('Map columns from {0} to fields in {1}', parts)}
					</div>
				`
			},
			{
				fieldtype: 'Section Break'
			}
		].concat(fields);

		let dialog = new frappe.ui.Dialog({
			title: __('Map Columns'),
			fields,
			primary_action: values => {
				let changed_map = {};
				changed.map(i => {
					let header_row_index = i - 1;
					changed_map[header_row_index] = values[i];
				});
				if (changed.length > 0) {
					this.events.remap_column(changed_map);
				}
				dialog.hide();
			}
		});
		dialog.$body.addClass('map-columns');
		dialog.show();
	}

	is_row_imported(row) {
		let serial_no = row[0].content;
		return this.import_log.find(log => {
			return log.success && log.row_indexes.includes(serial_no);
		});
	}
};

function get_fields_as_options(doctype, column_map) {
	let keys = [doctype];
	frappe.meta.get_table_fields(doctype).forEach(df => {
		keys.push(df.fieldname);
	});
	// flatten array
	return [].concat(
		...keys.map(key => {
			return column_map[key].map(df => {
				let label = df.label;
				let value = df.fieldname;
				if (doctype !== key) {
					let table_field = frappe.meta.get_docfield(doctype, key);
					label = `${df.label} (${table_field.label})`;
					value = `${table_field.fieldname}.${df.fieldname}`;
				}
				return {
					label,
					value,
					description: value
				};
			});
		})
	);
}