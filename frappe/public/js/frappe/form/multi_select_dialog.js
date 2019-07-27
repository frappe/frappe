// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.MultiSelectDialog = Class.extend({
	init: function(opts) {
		/* Options: doctype, target, setters, get_query, action */
		$.extend(this, opts);

		var me = this;
		if(this.doctype!="[Select]") {
			frappe.model.with_doctype(this.doctype, function(r) {
				me.make();
			});
		} else {
			this.make();
		}
	},
	make: function() {
		let me = this;

		this.page_length = 20;
		this.start = 0;

		let fields = [
			{
				fieldtype: "Data",
				label: __("Search Term"),
				fieldname: "search_term"
			},
			{
				fieldtype: "Column Break"
			}
		];
		let count = 0;
		if(!this.date_field) {
			this.date_field = "transaction_date";
		}

		// setters can be defined as a dict or a list of fields
		// setters define the additional filters that get applied
		// for selection

		// CASE 1: DocType name and fieldname is the same, example "customer" and "customer"
		// setters define the filters applied in the modal
		// if the fieldnames and doctypes are consistently named,
		// pass a dict with the setter key and value, for example
		// {customer: [customer_name]}

		// CASE 2: if the fieldname of the target is different,
		// then pass a list of fields with appropriate fieldname

		if($.isArray(this.setters)) {
			for (let df of this.setters) {
				fields.push(df, {fieldtype: "Column Break"});
			}
		} else {
			Object.keys(this.setters).forEach(function(setter) {
				fields.push({
					fieldtype: me.target.fields_dict[setter].df.fieldtype,
					label: me.target.fields_dict[setter].df.label,
					fieldname: setter,
					options: me.target.fields_dict[setter].df.options,
					default: me.setters[setter]
				});
				if (count++ < Object.keys(me.setters).length) {
					fields.push({fieldtype: "Column Break"});
				}
			});
		}

		fields = fields.concat([
			{
				"fieldname":"date_range",
				"label": __("Date Range"),
				"fieldtype": "DateRange",
			},
			{ fieldtype: "Section Break" },
			{ fieldtype: "HTML", fieldname: "results_area" },
			{ fieldtype: "Button", fieldname: "more_btn", label: __("More"),
				click: function(){
					me.start += 20;
					frappe.flags.auto_scroll = true;
					me.get_results();
				}
			}
		]);

		let doctype_plural = !this.doctype.endsWith('y') ? this.doctype + 's'
			: this.doctype.slice(0, -1) + 'ies';
		this.dialog = new frappe.ui.Dialog({
			title: __("Select {0}", [(this.doctype=='[Select]') ? __("value") : __(doctype_plural)]),
			fields: fields,
			primary_action_label: __("Get Items"),
			secondary_action_label: __("Make {0}", [me.doctype]),
			primary_action: function() {
				me.action(me.get_checked_values(), me.args);
			},
			secondary_action: function(e) {
				// If user wants to close the modal
				if (e) {
					frappe.route_options = {};
					if($.isArray(me.setters)) {
						for (let df of me.setters) {
							frappe.route_options[df.fieldname] = me.dialog.fields_dict[df.fieldname].get_value() || undefined;
						}
					} else {
						Object.keys(me.setters).forEach(function(setter) {
							frappe.route_options[setter] = me.dialog.fields_dict[setter].get_value() || undefined;
						});
					}

					frappe.new_doc(me.doctype, true);
				}
			}
		});

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

	bind_events: function() {
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

		this.$parent.find('[data-fieldname="date_range"]').on('blur', (e) => {
			frappe.flags.auto_scroll = false;
			this.get_results();
		});

		this.$parent.find('[data-fieldname="search_term"]').on('input', (e) => {
			var $this = $(this);
			clearTimeout($this.data('timeout'));
			$this.data('timeout', setTimeout(function() {
				frappe.flags.auto_scroll = false;
				me.empty_list();
				me.get_results();
			}, 300));
		});
	},

	get_checked_values: function() {
		return this.$results.find('.list-item-container').map(function() {
			if ($(this).find('.list-row-check:checkbox:checked').length > 0 ) {
				return $(this).attr('data-item-name');
			}
		}).get();
	},

	make_list_row: function(result={}) {
		var me = this;
		// Make a head row by default (if result not passed)
		let head = Object.keys(result).length === 0;

		let contents = ``;
		let columns = ["name"];

		if($.isArray(this.setters)) {
			for (let df of this.setters) {
				columns.push(df.fieldname);
			}
		} else {
			columns = columns.concat(Object.keys(this.setters));
		}
		columns.push("Date");

		columns.forEach(function(column) {
			contents += `<div class="list-item__content ellipsis">
				${
					head ? `<span class="ellipsis">${__(frappe.model.unscrub(column))}</span>`

					: (column !== "name" ? `<span class="ellipsis">${__(result[column])}</span>`
						: `<a href="${"#Form/"+ me.doctype + "/" + result[column]}" class="list-id ellipsis">
							${__(result[column])}</a>`)
				}
			</div>`;
		})

		let $row = $(`<div class="list-item">
			<div class="list-item__content" style="flex: 0 0 10px;">
				<input type="checkbox" class="list-row-check" data-item-name="${result.name}" ${result.checked ? 'checked' : ''}>
			</div>
			${contents}
		</div>`);


		head ? $row.addClass('list-item--head')
			: $row = $(`<div class="list-item-container" data-item-name="${result.name}"></div>`).append($row);
		return $row;
	},

	render_result_list: function(results, more = 0) {
		var me = this;
		var more_btn = me.dialog.fields_dict.more_btn.$wrapper;

		// Make empty result set if filter is set
		if (!frappe.flags.auto_scroll) {
			this.empty_list();
		}
		more_btn.hide();

		if (results.length === 0) return;
		if (more) more_btn.show();

		results.forEach((result) => {
			me.$results.append(me.make_list_row(result));
		});

		if (frappe.flags.auto_scroll) {
			this.$results.animate({scrollTop: me.$results.prop('scrollHeight')}, 500);
		}
	},

	empty_list: function() {
		this.$results.find('.list-item-container').remove();
	},

	get_results: function() {
		let me = this;

		let filters = this.get_query ? this.get_query().filters : {};
		let filter_fields = [me.date_field];
		if($.isArray(this.setters)) {
			for (let df of this.setters) {
				filters[df.fieldname] = me.dialog.fields_dict[df.fieldname].get_value() || undefined;
				me.args[df.fieldname] = filters[df.fieldname];
				filter_fields.push(df.fieldname);
			}
		} else {
			Object.keys(this.setters).forEach(function(setter) {
				filters[setter] = me.dialog.fields_dict[setter].get_value() || undefined;
				me.args[setter] = filters[setter];
				filter_fields.push(setter);
			});
		}

		let date_val = this.dialog.fields_dict["date_range"].get_value();
		if(date_val) {
			filters[this.date_field] = ['between', date_val];
		}

		let args = {
			doctype: me.doctype,
			txt: me.dialog.fields_dict["search_term"].get_value(),
			filters: filters,
			filter_fields: filter_fields,
			start: this.start,
			page_length: this.page_length + 1,
			query: this.get_query ? this.get_query().query : '',
			as_dict: 1
		}
		frappe.call({
			type: "GET",
			method:'frappe.desk.search.search_widget',
			no_spinner: true,
			args: args,
			callback: function(r) {
				let results = [], more = 0;
				if (r.values.length) {
					if (r.values.length > me.page_length) {
						r.values.pop();
						more = 1;
					}
					r.values.forEach(function(result) {
						if(me.date_field in result) {
							result["Date"] = result[me.date_field]
						}
						result.checked = 0;
						result.parsed_date = Date.parse(result["Date"]);
						results.push(result);
					});
					results.map( (result) => {
						result["Date"] = frappe.format(result["Date"], {"fieldtype":"Date"});
					})

					results.sort((a, b) => {
						return a.parsed_date - b.parsed_date;
					});

					// Preselect oldest entry
					if (me.start < 1 && r.values.length === 1) {
						results[0].checked = 1;
					}
				}
				me.render_result_list(results, more);
			}
		});
	},

});