frappe.provide('frappe.views');

frappe.ui.GroupBy = class {
	constructor(report_view) {
		this.report_view = report_view;
		this.page = report_view.page;
		this.doctype = report_view.doctype;
		this.make();
	}

	make() {
		this.make_group_by_button();
		this.init_group_by_popover();
		this.set_popover_events();
	}

	init_group_by_popover() {
		const sql_aggregate_functions = [
			{name: 'count', label: __('Count')},
			{name: 'sum', label: __('Sum')},
			{name: 'avg', label: __('Average')}
		];

		const group_by_template = $(
			frappe.render_template('group_by', {
				doctype: this.doctype,
				group_by_conditions: this.get_group_by_fields(),
				aggregate_function_conditions: sql_aggregate_functions,
			})
		);

		this.group_by_button.popover({
			content: group_by_template,
			template: `
				<div class="group-by-popover popover">
					<div class="arrow"></div>
					<div class="popover-body popover-content">
					</div>
				</div>
			`,
			html: true,
			trigger: 'manual',
			container: 'body',
			placement: 'bottom',
			offset: '-100px 0',
		});
	}

	trigger_on_change() {
		this.report_view.on_group_by_change(this.get());
	}

	// TODO: make common with filter popover
	set_popover_events() {
		$(document.body).on('click', (e) => {
			if (this.wrapper && this.wrapper.is(':visible')) {
				if (
					$(e.target).parents('.group-by-popover').length === 0 &&
					$(e.target).parents('.group-by-box').length === 0 &&
					$(e.target).parents('.group-by-button').length === 0 &&
					!$(e.target).is(this.group_by_button)
				) {
					this.wrapper && this.group_by_button.popover('hide');
				}
			}
		});

		this.group_by_button.on('click', () => {
			this.group_by_button.popover('toggle');
		});

		this.group_by_button.on('shown.bs.popover', () => {
			if (!this.wrapper) {
				this.wrapper = $('.group-by-popover');
				this.setup_group_by_area();
			}
		});

		this.group_by_button.on('hidden.bs.popover', () => {
			this.update_group_by_button();
		});

		frappe.router.on('change', () => {
			this.group_by_button.popover('hide');
		});
	}

	setup_group_by_area() {
		this.aggregate_on_html = ``;
		this.group_by_select = this.wrapper.find('select.group-by');
		this.group_by_field && this.group_by_select.val(this.group_by_field);
		this.aggregate_function_select = this.wrapper.find(
			'select.aggregate-function'
		);
		this.aggregate_on_select = this.wrapper.find('select.aggregate-on');
		this.remove_group_by_button = this.wrapper.find('.remove-group-by');

		if (this.aggregate_function) {
			this.aggregate_function_select.val(this.aggregate_function);
		} else {
			// set default to count
			this.aggregate_function_select.val('count');
		}

		this.toggle_aggregate_on_field();
		this.update_group_by_button();
		this.aggregate_on && this.aggregate_on_select.val(this.aggregate_on_field);
		this.set_group_by_events();
	}

	set_group_by_events() {
		// try running fon change
		this.group_by_select.on('change', () => {
			this.group_by_field = this.group_by_select.val();
			this.group_by_doctype = this.group_by_select
				.find(':selected')
				.attr('data-doctype');
			if (this.is_valid()) {
				this.trigger_on_change()
			}
		});

		this.aggregate_function_select.on('change', () => {
			//Set aggregate on options as numeric fields if function is sum or average
			this.toggle_aggregate_on_field();
			this.aggregate_function = this.aggregate_function_select.val();
			if (this.is_valid()) {
				this.trigger_on_change()
			}
		});

		this.aggregate_on_select.on('change', () => {
			this.aggregate_on_field = this.aggregate_on_select.val();
			this.aggregate_on_doctype = this.aggregate_on_select
				.find(':selected')
				.attr('data-doctype');
			if (this.is_valid()) {
				this.trigger_on_change()
			}
		});

		this.remove_group_by_button.on('click', () => {
			if (this.group_by_field) {
				this.set(null);
				this.trigger_on_change();
				this.toggle_aggregate_on_field_display(false);
			}
		});
	}

	toggle_aggregate_on_field() {
		let fn = this.aggregate_function_select.val();
		if (fn === 'sum' || fn === 'avg') {
			if (!this.aggregate_on_html.length) {
				this.aggregate_on_html = `<option value="" disabled selected>
						${__('Select Field...')}
					</option>`;

				for (let doctype in this.all_fields) {
					const doctype_fields = this.all_fields[doctype];
					doctype_fields.forEach((field) => {
						// pick numeric fields for sum / avg
						if (frappe.model.is_numeric_field(field.fieldtype)) {
							let option_text =
								doctype == this.doctype
									? field.label
									: `${field.label} (${__(doctype)})`;
							this.aggregate_on_html += `<option data-doctype="${doctype}"
								value="${field.fieldname}">${__(option_text)}</option>`;
						}
					});
				}
			}
			this.aggregate_on_select.html(this.aggregate_on_html);
			this.toggle_aggregate_on_field_display(true);
		} else {
			// count, so no aggregate function
			this.toggle_aggregate_on_field_display(false);
		}
	}

	//TODO: Fix this
	toggle_aggregate_on_field_display(show) {
		this.group_by_select.parent().toggleClass('col-sm-5', show);
		this.group_by_select.parent().toggleClass('col-sm-8', !show);
		this.aggregate_function_select.parent().toggleClass('col-sm-2', show);
		this.aggregate_function_select.parent().toggleClass('col-sm-3', !show);
		this.aggregate_on_select.parent().toggle(show);
	}

	get() {
		if (this.group_by_field) {
			return {
				group_by: [this.group_by_field, this.group_by_doctype],
				aggregate_function: this.aggregate_function,
				aggregate_on: [this.aggregate_on_field, this.aggregate_on_doctype]
			};
		} else {
			return null;
		}
	}

	set(value) {
		if (value && value.group_by) {
			this.group_by_field = value.group_by[0]
			this.group_by_doctype = value.group_by[1]
		} else {
			this.group_by_field = null;
			this.group_by_doctype = null;
		}

		if (value && value.aggregate_on) {
			this.aggregate_on_field = value.aggregate_on[0]
			this.aggregate_on_doctype = value.aggregate_on[1]
		} else {
			this.aggregate_on_field = null;
			this.aggregate_on_doctype = null;
		}

		this.aggregate_function = value && value.aggregate_function || 'count'

		this.update_group_by_button();
	}

	make_group_by_button() {
		this.page.wrapper.find('.sort-selector').before(
			$(`<div class="group-by-selector">
				<button class="btn btn-default btn-sm group-by-button ellipsis">
					<span class="group-by-icon">
						${frappe.utils.icon('group-by')}
					</span>
					<span class="button-label hidden-xs">
						${__('Add Group')}
					</span>
				</button>
			</div>`)
		);

		this.group_by_button = this.page.wrapper.find('.group-by-button');
	}

	is_valid() {
		if (this.aggregate_function === 'count') {
			this.aggregate_on_field = null;
			this.aggregate_on_doctype = null;
		}

		//All necessary fields must be set before applying group by
		if (
			!this.group_by_field ||
			!this.aggregate_function ||
			(!this.aggregate_on_field && this.aggregate_function !== 'count')
		) {
			return false;
		}

		return true;
	}

	get_group_by_fields() {
		this.group_by_fields = {};
		this.all_fields = {};

		const fields = this.report_view.meta.fields.filter((f) =>
			['Select', 'Link', 'Data', 'Int', 'Check'].includes(f.fieldtype)
		);
		const tag_field = {fieldname: '_user_tags', fieldtype: 'Data', label: __('Tags')};
		this.group_by_fields[this.doctype] = fields.concat(tag_field);
		this.all_fields[this.doctype] = this.report_view.meta.fields;

		const standard_fields_filter = (df) =>
			!in_list(frappe.model.no_value_type, df.fieldtype) && !df.report_hide;

		const table_fields = frappe.meta
			.get_table_fields(this.doctype)
			.filter((df) => !df.hidden);

		table_fields.forEach((df) => {
			const cdt = df.options;
			const child_table_fields = frappe.meta
				.get_docfields(cdt)
				.filter(standard_fields_filter);
			this.group_by_fields[cdt] = child_table_fields;
			this.all_fields[cdt] = child_table_fields;
		});

		return this.group_by_fields;
	}

	update_group_by_button() {
		const group_by_applied = Boolean(this.group_by_field);
		const button_label = group_by_applied
			? __("Group By {0}", [this.get_group_by_field_label()])
			: __('Add Group');

		if (this.wrapper) {
			this.group_by_select.val(this.group_by_field);
			this.aggregate_function_select.val(this.aggregate_function);
			this.aggregate_on_select.val(this.aggregate_on_field);
		}

		this.group_by_button
			.toggleClass('btn-default', !group_by_applied)
			.toggleClass('btn-primary-light', group_by_applied);

		this.group_by_button.find('.group-by-icon')
			.toggleClass('active', group_by_applied);

		this.group_by_button.find('.button-label').html(button_label);
		this.group_by_button.attr('title', button_label);
	}

	get_group_by_field_label() {
		return this.group_by_fields[this.group_by_doctype].find(
			field => field.fieldname == this.group_by_field
		).label;
	}
};
