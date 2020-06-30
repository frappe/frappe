frappe.ui.form.MultiSelectDialog = class MultiSelectDialog {
	constructor(opts) {
		/* Options: doctype, target, setters, get_query, action, add_filters_group, data_fields, primary_action_label */
		Object.assign(this, opts);
		var me = this;
		if (this.doctype != "[Select]") {
			frappe.model.with_doctype(this.doctype, function () {
				me.make();
			});
		} else {
			this.make();
		}
	}

	make() {
		let me = this;
		this.page_length = 20;
		this.start = 0;

		// create filters
		this.selector = new frappe.ui.form.Selector();
		let fields = this.selector.get_filters(this.doctype, this.setters);
		if (this.add_filters_group) {
			fields.push(
				{
					fieldtype: 'HTML',
					fieldname: 'filter_area',
				}
			);
		}

		// Make results area
		fields = fields.concat([
			{ fieldtype: "HTML", fieldname: "results_area" },
			{
				fieldtype: "Button", fieldname: "more_btn", label: __("More"),
				click: () => {
					this.start += 20;
					this.get_results();
				}
			}
		]);

		// Custom Data Fields
		if (this.data_fields) {
			fields.push({ fieldtype: "Section Break" });
			fields = fields.concat(this.data_fields);
		}

		let doctype_plural = this.doctype.plural();

		this.dialog = new frappe.ui.Dialog({
			title: __("Select {0}", [(this.doctype == '[Select]') ? __("value") : __(doctype_plural)]),
			fields: fields,
			primary_action_label: this.primary_action_label || __("Get Items"),
			secondary_action_label: __("Make {0}", [me.doctype]),
			primary_action: function () {
				let filters_data = me.get_custom_filters();
				me.action(me.get_checked_values(), cur_dialog.get_values(), me.args, filters_data);
			},
			secondary_action: function (e) {
				// If user wants to close the modal
				if (e) {
					frappe.route_options = {};
					if (Array.isArray(me.setters)) {
						for (let df of me.setters) {
							frappe.route_options[df.fieldname] = me.dialog.fields_dict[df.fieldname].get_value() || undefined;
						}
					} else {
						Object.keys(me.setters).forEach(function (setter) {
							frappe.route_options[setter] = me.dialog.fields_dict[setter].get_value() || undefined;
						});
					}

					frappe.new_doc(me.doctype, true);
				}
			}
		});

		if (this.add_filters_group) {
			this.make_filter_area();
		}

		this.$parent = $(this.dialog.body);
		this.$wrapper = this.dialog.fields_dict.results_area.$wrapper.append(`<div class="results"
			style="border: 1px solid #d1d8dd; border-radius: 3px; height: 300px; overflow: auto;"></div>`);

		this.$results = this.$wrapper.find('.results');
		this.$results.append(this.selector.make_list_row(this.doctype, this.setters));

		this.args = {};

		this.bind_events();
		this.get_results();
		this.dialog.show();
	}

	make_filter_area() {
		this.filter_group = new frappe.ui.FilterGroup({
			parent: this.dialog.get_field('filter_area').$wrapper,
			doctype: this.doctype,
			on_change: () => {
				this.get_results();
			}
		});
	}

	get_custom_filters() {
		if (this.add_filters_group && this.filter_group) {
			return this.filter_group.get_filters().reduce((acc, filter) => {
				return Object.assign(acc, {
					[filter[1]]: [filter[2], filter[3]]
				});
			}, {});
		} else {
			return [];
		}
	}

	bind_events() {
		let me = this;

		this.$results.on('click', '.list-item-container', function (e) {
			if (!$(e.target).is(':checkbox') && !$(e.target).is('a')) {
				$(this).find(':checkbox').trigger('click');
			}
		});

		this.$results.on('click', '.list-item--head :checkbox', (e) => {
			this.$results.find('.list-item-container .list-row-check')
				.prop("checked", ($(e.target).is(':checked')));
		});

		this.$parent.find('.input-with-feedback').on('change', () => {
			frappe.flags.auto_scroll = false;
			this.get_results();
		});

		this.$parent.find('[data-fieldtype="Data"]').on('input', () => {
			var $this = $(this);
			clearTimeout($this.data('timeout'));
			$this.data('timeout', setTimeout(function () {
				frappe.flags.auto_scroll = false;
				me.empty_list();
				me.get_results();
			}, 300));
		});
	}

	get_checked_values() {
		// Return name of checked value.
		return this.$results.find('.list-item-container').map(function () {
			if ($(this).find('.list-row-check:checkbox:checked').length > 0) {
				return $(this).attr('data-item-name');
			}
		}).get();
	}

	get_checked_items() {
		// Return checked items with all the column values.
		let checked_values = this.get_checked_values();
		return this.results.filter(res => checked_values.includes(res.name));
	}

	render_result_list(results, more = 0, empty = true) {
		var me = this;
		var more_btn = me.dialog.fields_dict.more_btn.$wrapper;

		// Make empty result set if filter is set
		if (!frappe.flags.auto_scroll && empty) {
			this.empty_list();
		}
		more_btn.hide();

		if (results.length === 0) return;
		if (more) more_btn.show();

		let checked = this.get_checked_values();

		results
			.filter(result => !checked.includes(result.name))
			.forEach(result => {
				me.$results.append(me.selector.make_list_row(me.doctype, me.setters, result));
			});

		if (frappe.flags.auto_scroll) {
			this.$results.animate({ scrollTop: me.$results.prop('scrollHeight') }, 500);
		}
	}

	empty_list() {
		// Store all checked items
		let checked = this.get_checked_items().map(item => {
			return {
				...item,
				checked: true
			};
		});

		// Remove **all** items
		this.$results.find('.list-item-container').remove();

		// Rerender checked items
		this.render_result_list(checked, 0, false);
	}

	get_results() {
		let me = this;
		let filters = this.get_query ? this.get_query().filters : {} || {};
		let filter_fields = [];

		if ($.isArray(this.setters)) {
			for (let df of this.setters) {
				filters[df.fieldname] = me.dialog.fields_dict[df.fieldname].get_value() || undefined;
				me.args[df.fieldname] = filters[df.fieldname];
				filter_fields.push(df.fieldname);
			}
		} else {
			Object.keys(this.setters).forEach(function (setter) {
				var value = me.dialog.fields_dict[setter].get_value();
				if (me.dialog.fields_dict[setter].df.fieldtype == "Data" && value) {
					filters[setter] = ["like", "%" + value + "%"];
				} else {
					filters[setter] = value || undefined;
					me.args[setter] = filters[setter];
					filter_fields.push(setter);
				}
			});
		}

		let filter_group = this.get_custom_filters();
		Object.assign(filters, filter_group);

		let args = {
			doctype: me.doctype,
			txt: me.dialog.fields_dict["search_term"].get_value(),
			filters: filters,
			filter_fields: filter_fields,
			start: this.start,
			page_length: this.page_length + 1,
			query: this.get_query ? this.get_query().query : '',
			as_dict: 1
		};
		frappe.call({
			type: "GET",
			method: 'frappe.desk.search.search_widget',
			no_spinner: true,
			args: args,
			callback: function (r) {
				let more = 0;
				me.results = [];
				if (r.values.length) {
					if (r.values.length > me.page_length) {
						r.values.pop();
						more = 1;
					}
					r.values.forEach(function (result) {
						result.checked = 0;
						me.results.push(result);
					});
				}
				me.render_result_list(me.results, more);
			}
		});
	}
};