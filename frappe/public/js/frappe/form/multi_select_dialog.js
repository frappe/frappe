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

		let fields = [];
		let count = 0;
		if(!this.date_field) {
			this.date_field = "transaction_date";
		}
		Object.keys(this.setters).forEach(function(setter) {
			fields.push({
				fieldtype: me.target.fields_dict[setter].df.fieldtype,
				label: me.target.fields_dict[setter].df.label,
				fieldname: setter,
				options: me.target.fields_dict[setter].df.options,
				default: me.setters[setter]
			});
			if (count++ < Object.keys(me.setters).length - 1) {
				fields.push({fieldtype: "Column Break"});
			}
		});

		fields = fields.concat([
			{ fieldtype: "Section Break" },
			{ fieldtype: "HTML", fieldname: "results_area" },
			{ fieldtype: "Button", fieldname: "make_new", label: __("Make a new " + me.doctype) }
		]);

		let doctype_plural = !this.doctype.endsWith('y') ? this.doctype + 's'
			: this.doctype.slice(0, -1) + 'ies';

		this.dialog = new frappe.ui.Dialog({
			title: __("Select {0}", [(this.doctype=='[Select]') ? __("value") : __(doctype_plural)]),
			fields: fields,
			primary_action_label: __("Get Items"),
			primary_action: function() {
				me.action(me.get_checked_values(), me.args);
			}
		});

		this.$parent = $(this.dialog.body);
		this.$wrapper = this.dialog.fields_dict.results_area.$wrapper.append(`<div class="results"
			style="border: 1px solid #d1d8dd; border-radius: 3px; height: 300px; overflow: auto;"></div>`);
		this.$results = this.$wrapper.find('.results');
		this.$make_new_btn = this.dialog.fields_dict.make_new.$wrapper;

		this.$placeholder = $(`<div class="multiselect-empty-state">
					<span class="text-center" style="margin-top: -40px;">
						<i class="fa fa-2x fa-tags text-extra-muted"></i>
						<p class="text-extra-muted">No ${this.doctype} found</p>
						<button class="btn btn-default btn-xs text-muted" data-fieldtype="Button"
							data-fieldname="make_new" placeholder="" value="">Make a new ${this.doctype}</button>
					</span>
				</div>`);

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
			this.get_results();
		});
		this.$parent.on('click', '.btn[data-fieldname="make_new"]', (e) => {
			frappe.route_options = {};
			Object.keys(this.setters).forEach(function(setter) {
				frappe.route_options[setter] = me.dialog.fields_dict[setter].get_value() || undefined;
			});
			frappe.new_doc(this.doctype, true);
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
		let columns = (["name"].concat(Object.keys(this.setters))).concat("Date");
		columns.forEach(function(column) {
			contents += `<div class="list-item__content ellipsis">
				${
					head ? __(frappe.model.unscrub(column))

					: (column !== "name" ? __(result[column])
						: `<a href="${"#Form/"+ me.doctype + "/" + result[column]}" class="list-id">
							${__(result[column])}</a>`)
				}
			</div>`;
		})

		let $row = $(`<div class="list-item">
			<div class="list-item__content ellipsis" style="flex: 0 0 10px;">
				<input type="checkbox" class="list-row-check" ${result.checked ? 'checked' : ''}>
			</div>
			${contents}
		</div>`);

		head ? $row.addClass('list-item--head')
			: $row = $(`<div class="list-item-container" data-item-name="${result.name}"></div>`).append($row);
		return $row;
	},

	render_result_list: function(results) {
		var me = this;
		this.$results.empty();
		if(results.length === 0) {
			this.$make_new_btn.addClass('hide');
			this.$results.append(me.$placeholder);
			return;
		}
		this.$make_new_btn.removeClass('hide');

		this.$results.append(this.make_list_row());
		results.forEach((result) => {
			me.$results.append(me.make_list_row(result));
		})
	},

	get_results: function() {
		let me = this;

		let filters = this.get_query().filters;
		Object.keys(this.setters).forEach(function(setter) {
			filters[setter] = me.dialog.fields_dict[setter].get_value() || undefined;
			me.args[setter] = filters[setter];
		});

		let args = {
			doctype: me.doctype,
			txt: '',
			filters: filters,
			filter_fields: Object.keys(me.setters).concat([me.date_field])
		}
		frappe.call({
			type: "GET",
			method:'frappe.desk.search.search_widget',
			no_spinner: true,
			args: args,
			callback: function(r) {
				if(r.values) {
					let results = [];
					r.values.forEach(function(value_list) {
						let result = {};
						value_list.forEach(function(value, index){
							if(r.fields[index] === me.date_field) {
								result["Date"] = value;
							} else {
								result[r.fields[index]] = value;
							}
						});
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
					results[0].checked = 1

					me.render_result_list(results);
				}
			}
		});
	},

});