import ColumnPickerFields from './column_picker_fields';
frappe.provide('frappe.data_import');

frappe.data_import.DataExporter = class DataExporter {
	constructor(doctype) {
		this.doctype = doctype;
		frappe.model.with_doctype(doctype, () => {
			this.make_dialog();
		});
	}

	make_dialog() {
		this.dialog = new frappe.ui.Dialog({
			title: __('Export Data'),
			fields: [
				{
					fieldtype: 'Select',
					fieldname: 'export_records',
					label: __('Export Type'),
					options: [
						{
							label: __('All Records'),
							value: 'all'
						},
						{
							label: __('Filtered Records'),
							value: 'by_filter'
						},
						{
							label: __('5 Records'),
							value: '5_records'
						},
						{
							label: __('Blank Template'),
							value: 'blank_template'
						}
					],
					default: 'blank_template',
					change: () => {
						this.update_record_count_message();
					}
				},
				{
					fieldtype: 'HTML',
					fieldname: 'filter_area',
					depends_on: doc => doc.export_records === 'by_filter'
				},
				{
					fieldtype: 'Select',
					fieldname: 'file_type',
					label: __('File Type'),
					options: ['Excel', 'CSV'],
					default: 'CSV'
				},
				{
					fieldtype: 'Section Break'
				},
				{
					fieldtype: 'HTML',
					fieldname: 'select_all_buttons'
				},
				{
					label: __(this.doctype),
					fieldname: this.doctype,
					fieldtype: 'MultiCheck',
					columns: 2,
					on_change: () => this.update_primary_action(),
					options: this.get_multicheck_options(this.doctype)
				},
				...frappe.meta.get_table_fields(this.doctype)
					.map(df => {
						let doctype = df.options;
						let label = df.reqd
							? __('{0} (1 row mandatory)', [doctype])
							: __(doctype);
						return {
							label,
							fieldname: doctype,
							fieldtype: 'MultiCheck',
							columns: 2,
							on_change: () => this.update_primary_action(),
							options: this.get_multicheck_options(doctype)
						};
					})
			],
			primary_action_label: __('Export'),
			primary_action: values => this.export_records(values),
			on_page_show: () => this.select_mandatory()
		});

		this.make_filter_area();
		this.make_select_all_buttons();
		this.update_record_count_message();

		this.dialog.show();
	}

	export_records() {
		let method =
			'/api/method/frappe.core.doctype.data_import_beta.data_import_beta.download_template';

		let multicheck_fields = this.dialog.fields
			.filter(df => df.fieldtype === 'MultiCheck')
			.map(df => df.fieldname);

		let values = this.dialog.get_values();

		let doctype_field_map = Object.assign({}, values);
		for (let key in doctype_field_map) {
			if (!multicheck_fields.includes(key)) {
				delete doctype_field_map[key];
			}
		}

		let filters = null;
		if (values.export_records === 'by_filter') {
			filters = this.get_filters();
		}

		open_url_post(method, {
			doctype: this.doctype,
			file_type: values.file_type,
			export_records: values.export_records,
			export_fields: doctype_field_map,
			export_filters: filters
		});
	}

	make_filter_area() {
		this.filter_group = new frappe.ui.FilterGroup({
			parent: this.dialog.get_field('filter_area').$wrapper,
			doctype: this.doctype,
			on_change: () => {
				this.update_record_count_message();
			}
		});
	}

	make_select_all_buttons() {
		let $select_all_buttons = $(`
			<div>
				<h6 class="form-section-heading uppercase">${__('Select fields to export')}</h6>
				<button class="btn btn-default btn-xs" data-action="select_all">
					${__('Select All')}
				</button>
				<button class="btn btn-default btn-xs" data-action="select_mandatory">
					${__('Select Mandatory')}
				</button>
				<button class="btn btn-default btn-xs" data-action="unselect_all">
					${__('Unselect All')}
				</button>
			</div>
		`);
		frappe.utils.bind_actions_with_object($select_all_buttons, this);
		this.dialog
			.get_field('select_all_buttons')
			.$wrapper.html($select_all_buttons);
	}

	select_all() {
		this.dialog.$wrapper
			.find(':checkbox')
			.prop('checked', true)
			.trigger('change');
	}

	select_mandatory() {
		let mandatory_table_doctypes = frappe.meta
			.get_table_fields(this.doctype)
			.filter(df => df.reqd)
			.map(df => df.options);
		mandatory_table_doctypes.push(this.doctype);

		let multicheck_fields = this.dialog.fields
			.filter(df => df.fieldtype === 'MultiCheck')
			.map(df => df.fieldname)
			.filter(doctype => mandatory_table_doctypes.includes(doctype));

		let checkboxes = [].concat(
			...multicheck_fields.map(fieldname => {
				let field = this.dialog.get_field(fieldname);
				return field.options
					.filter(option => option.danger)
					.map(option => option.$checkbox.find('input').get(0));
			})
		);

		this.unselect_all();
		$(checkboxes)
			.prop('checked', true)
			.trigger('change');
	}

	unselect_all() {
		this.dialog.$wrapper
			.find(':checkbox')
			.prop('checked', false)
			.trigger('change');
	}

	update_record_count_message() {
		let export_records = this.dialog.get_value('export_records');
		let count_method = {
			all: () => frappe.db.count(this.doctype),
			by_filter: () =>
				frappe.db.count(this.doctype, {
					filters: this.get_filters()
				}),
			blank_template: () => Promise.resolve(0),
			'5_records': () => Promise.resolve(5)
		};

		count_method[export_records]().then(value => {
			let message = '';
			value = parseInt(value, 10);
			if (value === 0) {
				message = __('No records will be exported');
			} else if (value === 1) {
				message = __('1 record will be exported');
			} else {
				message = __('{0} records will be exported', [value]);
			}
			this.dialog.set_df_property('export_records', 'description', message);

			this.update_primary_action(value);
		});
	}

	update_primary_action(no_of_records) {
		let $primary_action = this.dialog.get_primary_btn();

		if (no_of_records != null) {
			let label = '';
			if (no_of_records === 0) {
				label = __('Export');
			} else if (no_of_records === 1) {
				label = __('Export 1 record');
			} else {
				label = __('Export {0} records', [no_of_records]);
			}
			$primary_action.html(label);
		} else {
			let parent_fields = this.dialog.get_value(this.doctype);
			$primary_action.prop('disabled', parent_fields.length === 0);
		}
	}

	get_filters() {
		return this.filter_group.get_filters().reduce((acc, filter) => {
			return Object.assign(acc, {
				[filter[1]]: [filter[2], filter[3]]
			});
		}, {});
	}

	get_multicheck_options(doctype) {
		if (!this.column_map) {
			this.column_map = new ColumnPickerFields({
				doctype: this.doctype
			}).get_columns_for_picker();
		}

		let autoname_field = null;
		let meta = frappe.get_meta(doctype);
		if (meta.autoname && meta.autoname.startsWith('field:')) {
			let fieldname = meta.autoname.slice('field:'.length);
			autoname_field = frappe.meta.get_field(doctype, fieldname);
		}

		return this.column_map[doctype]
			.filter(df => {
				if (autoname_field && df.fieldname === autoname_field.fieldname) {
					return false;
				}
				return true;
			})
			.map(df => {
				let label = __(df.label);
				if (autoname_field && df.fieldname === 'name') {
					label = label + ` (${__(autoname_field.label)})`;
				}
				return {
					label,
					value: df.fieldname,
					danger: df.reqd,
					checked: false,
					description: `${df.fieldname} ${df.reqd ? __('(Mandatory)') : ''}`
				};
			});
	}
};
