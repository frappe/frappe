// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.LinkSelector = class {
	constructor (opts) {
		/* help: Options: doctype, get_query, target */
		// doctype, setters, get_query, on_select(action), view
		$.extend(this, opts);

		this.get_image_field() ? this.view = "Card View" : this.view = "List View";

		var me = this;
		if (this.doctype != "[Select]") {
			frappe.model.with_doctype(this.doctype, function (r) {
				me.make();
			});
		} else {
			this.make();
		}
	}

	make () {
		var me = this;

		// create filter fields
		this.selector = new frappe.ui.form.Selector();
		let fields = this.selector.get_filters(this.doctype, this.setters);
		fields = fields.concat([
			{ fieldtype: "HTML", fieldname: "results_area" }
		]);

		let doctype_plural = this.doctype.plural();

		this.dialog = new frappe.ui.Dialog({
			title: __("Select {0}", [(this.doctype == '[Select]') ? __("value") : __(doctype_plural)]),
			fields: fields,
			primary_action_label: __("Search"),
			primary_action: function () {
				me.get_results();
			}
		});

		this.$parent = $(this.dialog.body);
		this.$results_area = me.dialog.fields_dict.results_area.$wrapper;

		if (this.txt)
			this.dialog.fields_dict.search_term.set_input(this.txt);

		this.start = 0;
		this.bind_events();
		this.get_results();
		this.dialog.show();
	}

	get_image_field () {
		// Check if doctype has image field
		return false;
	}

	bind_events () {
		var me = this;

		this.$parent.find('.input-with-feedback').on('change', () => {
			frappe.flags.auto_scroll = false;
			this.get_results();
		});

		this.dialog.get_input("search_term").on("keypress", function (e) { //check if useful
			if (e.which === 13) {
				// me.start = 0;
				me.get_results();
			}
		});
	}

	get_results () {
		let me = this;
		let filters = this.get_query ? this.get_query().filters : {} || {};
		let filter_fields = [];

		Object.keys(this.setters).forEach(function (setter) {
			var value = me.dialog.fields_dict[setter].get_value();
			if (me.dialog.fields_dict[setter].df.fieldtype == "Data" && value) {
				filters[setter] = ["like", "%" + value + "%"];
			} else {
				filters[setter] = value || undefined;
				//me.args[setter] = filters[setter];
				filter_fields.push(setter);
			}
		});

		var args = {
			doctype: this.doctype,
			txt: this.dialog.fields_dict.search_term.get_value() || '',
			filters: filters,
			filter_fields: ["image", ...filter_fields],
			page_length: this.page_length + 1,
			start: this.start,
			query: this.get_query ? this.get_query().query : '',
			as_dict: 1
		};

		frappe.call({
			method: "frappe.desk.search.search_widget",
			type: "GET",
			no_spinner: true,
			args: args,
			callback: function (r) {
				me.render_results(r);
			},
			btn: this.dialog.get_primary_btn()
		});
	}

	render_results (results) {
		var me = this;
		this.$results_area.empty();

		if (results && results.values.length) {
			// Render card/list view and bind action to checkboxes
			this.view === "Card View" ? this.render_card_view(results) : this.render_list_view(results);

			// bind primary action to each checkbox
			var checkboxes = this.$wrapper.find(this.checkbox_class);
			for (let checkbox of checkboxes) {
				checkbox.addEventListener('click', () => {
					if (checkbox.checked) {
						// Pass result name to primary action
						me.action(checkbox.getAttribute("data-name"));
					}
				});
			}
		} else {
			// No Results View
			$('<p style="text-align: center;"><br><span class="text-muted">' + __("No Results") + '</span>'
				+ (frappe.model.can_create(this.doctype) ?
					('<br><br><a class="new-doc btn btn-default btn-sm">'
						+ __('Create a new {0}', [__(this.doctype)]) + "</a>") : '')
				+ '</p>').appendTo(this.$results_area).find(".new-doc").click(function () {
				frappe.new_doc(me.doctype);
			});
		}
	}

	render_card_view (results) {
		var me = this;
		this.$results_area.append(`<div class="grid-container"></div>`);

		var $wrapper = this.$results_area.find(".grid-container");

		// take first two setters as card additional information
		let card_fields = Object.keys(this.setters).slice(0, 2);
		let columns = ["name", ...card_fields];

		$.each(results.values, function (i, result) {
			$wrapper.append(me.selector.make_card(columns, result));
		});

		this.checkbox_class = ".Check";
		this.$wrapper = this.$results_area.find(".grid-container");
	}

	render_list_view (results) {
		var me = this;

		this.$results_area.append(`<div class="results"
			style="border: 1px solid #d1d8dd; border-radius: 3px; height: 300px; overflow: auto;"></div>`);
		this.$results = this.$results_area.find('.results');
		this.$results.append(this.selector.make_list_row(this.doctype, this.setters));

		results.values.forEach(result => {
			me.$results.append(me.selector.make_list_row(me.doctype, me.setters, result));
		});

		this.checkbox_class = ".list-row-check";
		this.$wrapper = this.$results_area.find(".results");
	}

	action (name) {
		// for testing
		frappe.prompt({
			fieldname: "qty", fieldtype: "Float", label: "Qty",
			default: 1,
			reqd: 1
		});
	}
};
