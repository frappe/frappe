frappe.ui.form.MultiSelectDialog = Class.extend({
	init: function (opts) {
		/* Options: doctype, target, setters, get_query, action, add_filters_group, data_fields, primary_action_label */
		$.extend(this, opts);
		var me = this;
		if (this.doctype != "[Select]") {
			frappe.model.with_doctype(this.doctype, function () {
				me.make();
			});
		} else {
			this.make();
		}
	},
	make: function () {
		let me = this;
		this.page_length = 20;
		this.start = 0;
		let fields = this.get_fields_for_header();
		if (this.add_filters_group) {
			fields.push(
				{
					fieldtype: 'HTML',
					fieldname: 'filter_area',
				}
			);
		}

		fields = fields.concat([
			{ fieldtype: "HTML", fieldname: "results_area" },
			{
				fieldtype: "Button", fieldname: "more_btn", label: __("More"),
				click: function () {
					me.start += 20;
					frappe.flags.auto_scroll = true;
					me.get_results();
				}
			}
		]);

		if (this.data_fields) {
			fields.push({ fieldtype: "Section Break" });
			fields = fields.concat(this.data_fields);
		}

		let doctype_plural =frappe.utils.get_doctype_plural(this.doctype);
		this.dialog = new frappe.ui.Dialog({
			title: __("Select {0}", [(this.doctype == '[Select]') ? __("value") : __(doctype_plural)]),
			fields: fields,
			primary_action_label: this.primary_action_label || __("Get Items"),
			secondary_action_label: __("Make {0}", [me.doctype]),
			primary_action: function () {
				let filters_data = me.get_filters();
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
		this.$results.append(this.make_list_row());

		this.args = {};

		this.bind_events();
		this.get_results();
		this.dialog.show();
	},

	get_fields_for_header: function () {
		let fields = [];
		let me = this;
		let columns = {};
		columns['col_0'] = [
			{
				fieldtype: "Data",
				label: __("Search Term"),
				fieldname: "search_term"
			}
		];
		columns['col_1'] = [];
		columns['col_2'] = [];

		// setters can be defined as a dict or a list of fields
		// setters define the additional filters that get applied
		// for selection

		// CASE 1: DocType name and fieldname is the same, example "customer" and "customer"
		// setters define the filters applied in the modal
		// if the fieldnames and doctypes are consistently named,
		// pass a dict with the setter key and value, for example
		// {customer: [customer_name]}

		// CASE 2: if the fieldname of the target is different,
		// then pass a list of fields with appropriate

		if (Array.isArray(this.setters)) {
			for (let df of this.setters) {
				fields.push(df, { fieldtype: "Column Break" });
			}
		} else {
			Object.keys(this.setters).forEach(function (setter, index) {
				let df_prop = frappe.meta.docfield_map[me.doctype][setter];
				columns['col_' + cstr((index + 1) % 3)].push({
					fieldtype: df_prop.fieldtype,
					label: df_prop.label,
					fieldname: setter,
					options: df_prop.options,
					default: me.setters[setter]
				});
			});
		}

		for (let i = 0; i < 3; i++) {
			fields = fields.concat(columns['col_' + cstr(i)]);
			if (i != 2) {
				fields = fields.concat({ fieldtype: "Column Break" });
			}
		}
		fields = fields.concat({ fieldtype: "Section Break" });
		return fields;
	},

	make_filter_area: function () {
		this.filter_group = new frappe.ui.FilterGroup({
			parent: this.dialog.get_field('filter_area').$wrapper,
			doctype: this.doctype,
			on_change: () => {
				this.get_results();
			}
		});
	},

	get_filters: function () {
		return this.filter_group.get_filters().reduce((acc, filter) => {
			return Object.assign(acc, {
				[filter[1]]: [filter[2], filter[3]]
			});
		}, {});
	},

	bind_events: function () {
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

		this.$parent.find('.input-with-feedback').on('change', (e) => {
			frappe.flags.auto_scroll = false;
			this.get_results();
		});
		this.$parent.find('[data-fieldname="search_term"]').on('input', (e) => {
			var $this = $(this);
			clearTimeout($this.data('timeout'));
			$this.data('timeout', setTimeout(function () {
				frappe.flags.auto_scroll = false;
				me.empty_list();
				me.get_results();
			}, 300));
		});
	},

	get_checked_values: function () {
		// Return name of checked value.
		return this.$results.find('.list-item-container').map(function () {
			if ($(this).find('.list-row-check:checkbox:checked').length > 0) {
				return $(this).attr('data-item-name');
			}
		}).get();
	},

	get_checked_items: function () {
		// Return checked items with all the column values.
		let checked_values = this.get_checked_values();
		return this.results.filter(res => checked_values.includes(res.name));
	},

	make_list_row: function (result = {}) {
		var me = this;
		// Make a head row by default (if result not passed)
		let head = Object.keys(result).length === 0;

		let contents = ``;
		let columns = ["name"];

		if (Array.isArray(this.setters)) {
			for (let df of this.setters) {
				columns.push(df.fieldname);
			}
		} else {
			columns = columns.concat(Object.keys(this.setters));
		}

		columns.forEach(function (column) {
			contents += `<div class="list-item__content ellipsis">
				${
				head ? `<span class="ellipsis">${__(frappe.model.unscrub(column))}</span>`
					: (column !== "name" ? `<span class="ellipsis">${__(result[column])}</span>`
						: `<a href="${"#Form/" + me.doctype + "/" + result[column]}" class="list-id ellipsis">
							${__(result[column])}</a>`)
				}
			</div>`;
		});

		let $row = $(`<div class="list-item">
			<div class="list-item__content" style="flex: 0 0 10px;">
				<input type="checkbox" class="list-row-check" data-item-name="${result.name}" ${result.checked ? 'checked' : ''}>
			</div>
			${contents}
		</div>`);

		head ? $row.addClass('list-item--head')
			: $row = $(`<div class="list-item-container" data-item-name="${result.name}"></div>`).append($row);

		$(".modal-dialog .list-item--head").css("z-index", 0);
		return $row;
	},

	render_result_list: function (results, more = 0, empty = true) {
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
				me.$results.append(me.make_list_row(result));
			});

		if (frappe.flags.auto_scroll) {
			this.$results.animate({ scrollTop: me.$results.prop('scrollHeight') }, 500);
		}
	},

	empty_list: function () {
		let checked = this.get_checked_items().map(item => {
			return {
				...item,
				checked: true
			};
		});
		this.$results.find('.list-item-container').remove();
		this.render_result_list(checked, 0, false);
	},

	get_results: function () {
		let me = this;

		let filters = this.get_query ? this.get_query().filters : {} || {};
		// let filter_fields = [me.date_field];
		let filter_fields = [];
		if (Array.isArray(this.setters)) {
			for (let df of this.setters) {
				filters[df.fieldname] = me.dialog.fields_dict[df.fieldname].get_value() || undefined;
				me.args[df.fieldname] = filters[df.fieldname];
				filter_fields.push(df.fieldname);
			}
		} else {
			Object.keys(this.setters).forEach(function (setter) {
				filters[setter] = me.dialog.fields_dict[setter].get_value() || undefined;
				me.args[setter] = filters[setter];
				filter_fields.push(setter);
			});
		}

		let filter_group = this.get_filters();
		$.extend(filters, filter_group);

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
						result.parsed_date = Date.parse(result["Date"]);
						me.results.push(result);
					});
					me.results.sort((a, b) => {
						return a.parsed_date - b.parsed_date;
					});

					// Preselect oldest entry
					if (me.start < 1 && r.values.length === 1) {
						me.results[0].checked = 1;
					}
				}
				me.render_result_list(me.results, more);
			}
		});
	},

});