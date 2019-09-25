import DataTable from 'frappe-datatable';
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
	constructor({ wrapper, doctype, preview_data, frm, import_log, events = {} }) {
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
		this.header_row = this.preview_data.header_row;
		this.fields = this.preview_data.fields;
		this.data = this.preview_data.data;
		this.max_rows_exceeded = this.preview_data.max_rows_exceeded;
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
					</div>
				</div>
			</div>
		`);
		frappe.utils.bind_actions_with_object(this.wrapper, this);

		this.$table_preview = this.wrapper.find('.table-preview');
	}

	prepare_columns() {
		this.columns = this.fields.map((df, i) => {
			let column_width = 120;
			let header_row_index = i - 1;
			if (df.skip_import) {
				let is_sr = df.label === 'Sr. No';
				let show_warnings_button = `<button class="btn btn-xs" data-action="show_column_warning" data-col="${i}">
					<i class="octicon octicon-stop"></i></button>`;
				if (!df.parent) {
					// increase column width for unidentified columns
					column_width += 50
				}
				let column_title = is_sr
					? df.label
					: `<span class="indicator red">
						${df.header_title || `<i>${__('Untitled Column')}</i>`}
						${!df.parent ? show_warnings_button : ''}
					</span>`;
				return {
					id: frappe.utils.get_random(6),
					name: df.label,
					content: column_title,
					skip_import: true,
					editable: false,
					focusable: false,
					align: 'left',
					header_row_index,
					width: is_sr ? 60 : column_width,
					format: (value, row, column, data) => {
						let html = `<div class="text-muted">${value}</div>`;
						if (is_sr && this.is_row_imported(row)) {
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
				content: `<span class="indicator green">${df.header_title || df.label}</span>`,
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
			layout: this.columns.length < 10 ? 'fluid' : 'fixed',
			cellHeight: 35,
			serialNoColumn: false,
			checkboxColumn: false,
			pasteFromClipboard: true,
			noDataMessage: no_data_message
		});

		if (this.data.length === 0) {
			this.datatable.style.setStyle('.dt-scrollable', {
				height: 'auto'
			});
		}

		this.datatable.style.setStyle('.dt-dropdown', {
			display: 'none'
		});
	}

	get_rows_as_csv_array() {
		return this.datatable.getRows().map(row => {
			return row.map(cell => cell.content);
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
			color: frappe.ui.color.get_color_shade('black', 'extra-light'),
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

		let html = actions.filter(action => action.condition).map(action => {
			return `<button class="btn btn-sm btn-default" data-action="${action.handler}">
					${action.label}
				</button>
			`;
		});

		this.wrapper.find('.table-actions').html(html);
	}

	export_errored_rows() {
		this.events.export_errored_rows();
	}

	show_warnings() {
		this.events.show_warnings();
	}

	show_column_warning(_, $target) {
		let $warning = this.frm
			.get_field('import_warnings').$wrapper
			.find(`[data-col=${$target.data('col')}]`);
		frappe.utils.scroll_to($warning, true, 30);
	}

	show_column_mapper() {
		let column_picker_fields = new ColumnPickerFields({
			doctype: this.doctype
		});
		let changed = [];
		let fields = this.fields.map((df, i) => {
			if (df.label === 'Sr. No') return [];

			let fieldname;
			if (df.skip_import) {
				fieldname = null;
			} else {
				fieldname = df.parent === this.doctype
					? df.fieldname
					: `${df.parent}:${df.fieldname}`;
			}
			return [
				{
					label: __('Column {0}', [i]),
					fieldtype: 'Data',
					default: df.header_title,
					fieldname: `Column ${i}`,
					read_only: 1
				},
				{
					fieldtype: 'Button',
					label: 'Skip Column',
					fieldname: 'skip_' + i,
					click: () => {
						let header_row_index = i - 1;
						this.events.skip_import(header_row_index);
					}
				},
				{
					fieldtype: 'Column Break'
				},
				{
					fieldtype: 'Autocomplete',
					fieldname: i,
					label: __('Select field'),
					max_items: Infinity,
					options: column_picker_fields.get_fields_as_options(),
					default: fieldname,
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
		let dialog = new frappe.ui.Dialog({
			title: __('Column Mapper'),
			fields,
			primary_action: (values) => {
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
		dialog.show();
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
