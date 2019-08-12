import DataTable from 'frappe-datatable';

frappe.provide('frappe.data_import');

frappe.data_import.ImportPreview = class ImportPreview {
	constructor(wrapper, doctype, preview_data) {
		frappe.import_preview = this;
		this.wrapper = wrapper;
		this.doctype = doctype;
		this.preview_fields = preview_data.fields;
		this.preview_data = preview_data.data;
		this.preview_warnings = preview_data.warnings;

		this.make_wrapper();
		this.prepare_columns();
		this.prepare_data();
		this.render_warnings();
		this.render_datatable();
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
		this.columns = this.preview_fields.map(df => {
			if (df.skip_import) {
				return {
					id: frappe.utils.get_random(6),
					name: df.label,
					skip_import: true,
					editable: false,
					focusable: false,
					format: (value, row, column, data) => {
						return `<div class="text-muted">${value}</div>`;
					}
				};
			}

			let column_title = df.label;
			if (this.doctype !== df.parent) {
				column_title = `${df.label} (${df.parent})`;
			}
			return {
				id: df.fieldname,
				name: column_title,
				df: df,
				editable: true
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

	render_warnings() {
		let warning_html = this.preview_warnings
			.map(warning => {
				return `<div style="line-height: 2">${warning}</div>`;
			})
			.join('');

		let html = `<div class="border text-muted padding rounded margin-bottom">${warning_html}</div>`;
		this.$warnings.html(html);
	}

	render_datatable() {
		this.datatable = new DataTable(this.$table_preview.get(0), {
			data: this.preview_data,
			columns: this.columns,
			layout: 'fixed',
			cellHeight: 35,
			serialNoColumn: false,
			checkboxColumn: true,
			pasteFromClipboard: true,
			headerDropdown: [
				{
					label: __('Change column mapping'),
					action: console.log
				},
				{
					label: __("Don't Import"),
					action: console.log
				}
			]
		});

		this.datatable.style.setStyle('.dt-dropdown__list-item:nth-child(-n+4)', {
			display: 'none'
		});
	}

	add_row() {
		this.preview_data.push([]);
		this.datatable.refresh(this.preview_data);
	}
};
