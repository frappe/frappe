
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
		this.report_view.setup_columns();
		let sql_aggregate_function = [{name:'count', label: 'Count'}, {name:'sum', label: 'Sum'}, {name:'avg', label:'Average'}];
		this.groupby_edit_area = $(frappe.render_template("group_by", {
			groupby_conditions: this.get_group_by_fields(),
			aggregate_function_conditions: sql_aggregate_function,
		}));
		$(".aggregate-function").val("count");
		this.page.wrapper.find(".frappe-list").append(
			this.groupby_edit_area);

		//Set aggregate on options as numeric fields if function is sum or average
		$('.aggregate-function').on('change', () => {
			this.report_view.meta.fields.forEach((field) => {
				let fn = $('.aggregate-function option:selected').val();
				if(fn === 'sum' || fn === 'avg') {
					if(frappe.model.is_numeric_field(field.fieldtype)) {
						$('.aggregate-on')
							.append($('<option>', { value : field.fieldname })
								.text(field.label));
					}
					$('.aggregate-on').show();
				} else {
					$('.aggregate-on').hide();
				}
			});
		});

		$('.set-groupby-and-run').on('click', () => {
			this.apply_group_by();
		});

		$('.remove-groupby').on('click', () => {
			this.remove_group_by();
		});
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
		this.group_by = this.page.wrapper.find('.groupby option:selected').val();
		this.aggregate_function = this.page.wrapper.find('.aggregate-function option:selected').val();
		this.aggregate_on = this.page.wrapper.find('.aggregate-on option:selected').val();

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

		//If chosen group by field is not in fields, push it to fields
		if(!this.report_view.columns.includes(this.group_by)) {
			this.report_view.fields.push(this.group_by);
		}

		//If function is count add a new field for count
		if(this.aggregate_function === 'count') {
			let group_by_query = 'count(' + this.report_view.field_type + '.'+ this.group_by+') as ' + this.group_by + '_Count';
			this.report_view.fields.push([group_by_query, this.doctype]);
			this.order_by = this.group_by + '_Count desc';
		} else {
			//If chosen 'aggregate on' field is not in fields, push it to fields
			if(!this.report_view.columns.includes(this.aggregate_on)) {
				this.report_view.fields.push(this.aggregate_on);
			}
			this.order_by = this.aggregate_on + ' desc';
		}

		$('.set-groupby-and-run').hide();

		//Get current columns so that they can be restored when group by is removed
		this.current_cols = this.report_view.columns;

		let remove_columns = this.report_view.columns.filter(column => ![this.aggregate_on, this.group_by].includes(column.field));
		remove_columns.forEach((col) => {
			this.report_view.remove_column_from_datatable(col);
		});

		if(this.report_view.columns[0]) {
			this.removed_previous_width = this.report_view.columns[0].docfield.width;
			this.report_view.columns[0].docfield.width = 400;
		}
	}

	remove_group_by() {
		this.report_view.columns[0].docfield.width = this.removed_previous_width;
		this.order_by = '';
		this.groupby_edit_area.hide();
		$('.set-groupby-and-run').show();
		this.group_by = null;
		this.aggregate_function = null;
		this.aggregate_on = null;
		$(".groupby").val("");
		$(".aggregate-function").val("count");
		$(".aggregate-on").val("").hide();
		//Add the removed columns
		this.current_cols.forEach((col, i) => {
			this.report_view.add_column_to_datatable(col.field, this.doctype, i);
		});
		this.report_view.fields.pop();
		this.report_view.setup_columns();
	}

	get_group_by_fields() {
		return this.report_view.meta.fields.filter((f)=> ["Select", "Link"].includes(f.fieldtype));
	}
};
