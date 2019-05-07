
frappe.provide('frappe.views');

frappe.ui.GroupBy = class {
	constructor(report_view) {
		this.report_view = report_view;
		this.page = report_view.page;
		this.doctype = report_view.doctype;
		this.setup_group_by_area();
	}

	setup_group_by_area() {
		this.make_group_by_button();
		let sql_aggregate_function = [
			{name:'count', label: 'Count'},
			{name:'sum', label: 'Sum'},
			{name:'avg', label:'Average'}
		];
		this.groupby_edit_area = $(frappe.render_template("group_by", {
			groupby_conditions: this.get_group_by_fields(),
			aggregate_function_conditions: sql_aggregate_function,
		}));

		this.groupby_select = this.groupby_edit_area.find('select.groupby');
		this.aggregate_function_select = this.groupby_edit_area.find('select.aggregate-function');
		this.aggregate_on_select = this.groupby_edit_area.find('select.aggregate-on');

		// set default to count
		this.aggregate_function_select.val("count");
		this.page.wrapper.find(".frappe-list").append(
			this.groupby_edit_area);

		//Set aggregate on options as numeric fields if function is sum or average
		this.aggregate_function_select.on('change', () => {
			this.show_hide_aggregate_on();
		});

		// try running on change
		this.groupby_select.on('change', () => this.apply_group_by_and_refresh());
		this.aggregate_function_select.on('change', () => this.apply_group_by_and_refresh());
		this.aggregate_on_select.on('change', () => this.apply_group_by_and_refresh());

		$('.set-groupby-and-run').on('click', () => {
			this.apply_group_by_and_refresh();
		});

		$('.remove-groupby').on('click', () => {
			this.remove_group_by();
		});
	}

	show_hide_aggregate_on() {
		this.report_view.meta.fields.forEach((field) => {
			let fn = this.aggregate_function_select.val();
			if(fn === 'sum' || fn === 'avg') {
				// pick numeric fields for sum / avg
				if(frappe.model.is_numeric_field(field.fieldtype)) {
					this.aggregate_on_select.append(
						$('<option>', { value : field.fieldname })
							.text(field.label));
				}
				this.aggregate_on_select.show();
			} else {
				// count, so no aggregate function
				this.aggregate_on_select.hide();
			}
		});
	}

	get_settings() {
		if (this.group_by)  {
			return {
				group_by: this.group_by,
				aggregate_function: this.aggregate_function,
				aggregate_on: this.aggregate_on
			};
		} else {
			return null;
		}
	}

	apply_settings(settings) {
		this.groupby_select.val(settings.group_by);
		this.aggregate_function_select.val(settings.aggregate_function);
		this.show_hide_aggregate_on();
		this.aggregate_on_select.val(settings.aggregate_on);
		this.groupby_edit_area.show();

		this.apply_group_by();
	}

	make_group_by_button() {
		let group_by_button =  $(`<div class="tag-groupby-area">
			<div class="active-tag-groupby">
				<button class="btn btn-default btn-xs add-groupby text-muted">
						${__("Add Group")}
				</button>
			</div>
		</div>`);
		this.page.wrapper.find(".sort-selector").before(group_by_button);
		group_by_button.click(() => this.groupby_edit_area.show());
	}

	apply_group_by() {
		this.group_by = this.groupby_select.val();
		this.aggregate_function = this.aggregate_function_select.val();

		if (this.aggregate_function === 'count') {
			this.aggregate_on = 'name';
		} else {
			this.aggregate_on = this.aggregate_on_select.val();
		}


		//All necessary fields must be set before applying group by
		if(!this.group_by) {
			this.page.wrapper.find('.groupby').focus();
			return;
		} else if(!this.aggregate_function) {
			this.page.wrapper.find('.aggregate-function').focus();
			return;
		} else if(!this.aggregate_on && this.aggregate_function!=='count') {
			this.page.wrapper.find('.aggregate-on').focus();
			return;
		}

		return true;

	}

	apply_group_by_and_refresh() {
		if (this.apply_group_by()) {
			this.report_view.refresh();
		}
	}

	set_args(args) {
		if (this.aggregate_function && this.group_by) {
			let aggregate_column;
			if(this.aggregate_function === 'count') {
				aggregate_column = 'count(1)';
			} else {
				aggregate_column = `${this.aggregate_function}(${this.aggregate_on})`;
			}

			this.report_view.group_by = this.group_by;
			this.report_view.sort_by = '_aggregate_column';
			this.report_view.sort_order = 'desc';

			// save orignial fields
			if(!this.report_view.fields.map(f => f[0]).includes('_aggregate_column')) {
				this.original_fields = this.report_view.fields.map(f => f);
			}

			this.report_view.fields = [
				[this.group_by, this.doctype]
			];

			// rebuild fields for group by
			args.fields = this.report_view.get_fields();

			// add aggregate column in both query args and report view
			this.report_view.fields.push(['_aggregate_column', this.doctype]);
			args.fields.push(aggregate_column + ' as _aggregate_column');

			// setup columns in datatable
			this.report_view.setup_columns();

			Object.assign(args, {
				with_comment_count: false,
				group_by: this.report_view.group_by || null,
				order_by: '_aggregate_column desc'
			});
		}

	}


	get_group_by_docfield() {
		// called from build_column
		let docfield;
		if (this.aggregate_function === 'count') {
			docfield = {
				fieldtype: 'Int',
				label: __('Count'),
				parent: this.doctype,
				width: 120
			};
		} else {
			// get properties of "aggregate_on", for example Net Total
			docfield = Object.assign({}, frappe.meta.docfield_map[this.doctype][this.aggregate_on]);
			if (this.aggregate_function === 'sum') {
				docfield.label = __('Sum of {0}', [docfield.label]);
			} else {
				docfield.label = __('Average of {0}', [docfield.label]);
			}
		}
		docfield.fieldname = '_aggregate_column';

		return docfield;
	}

	remove_group_by() {
		this.groupby_edit_area.hide();

		this.order_by = '';
		this.group_by = null;
		this.aggregate_function = null;
		this.aggregate_on = null;
		$(".groupby").val("");
		$(".aggregate-function").val("count");
		$(".aggregate-on").empty().val("").hide();

		// restore original fields
		if (this.original_fields) {
			this.report_view.fields = this.original_fields;
		} else {
			this.report_view.set_default_fields();
		}
		this.report_view.setup_columns();
		this.original_fields = null;
		this.report_view.refresh();
	}

	get_group_by_fields() {
		return this.report_view.meta.fields.filter((f)=> ["Select", "Link"].includes(f.fieldtype));
	}

};
