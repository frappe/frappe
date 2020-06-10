// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.LinkSelector = class {
	constructor (opts) {
		/* help: Options: doctype, get_query, target */
		// doctype, setters, get_query, on_select(action), view
		$.extend(this, opts);

		var me = this;
		if (this.doctype != "[Select]") {
			frappe.model.with_doctype(this.doctype, function (r) {
				me.make();
			});
		} else if (this.view == 'List View') {
			// make Multiselect List view
		} else {
			if (get_image_field()) {
				this.make();
			}
			else{
				// multiselect
			}
		}
	}

	make () {
		var me = this;

		// create filter fields (array of objects)
		let fields = this.get_filters();
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

		this.$grid_wrapper = this.$results_area.find(".grid-container");

		if (this.txt)
			this.dialog.fields_dict.search_term.set_input(this.txt);

		this.start = 0;
		this.bind_events();
		this.get_results();
		this.dialog.show();
	}

	get_image_field () {

	}

	get_filters () {
		let fields = [];
		let columns = new Array(3);

		// Hack for three column layout
		// To add column break
		columns[0] = [
			{
				fieldtype: "Data",
				label: __("Search"),
				fieldname: "search_term",
				description: __("You can use wildcard %")
			}
		];
		columns[1] = [];
		columns[2] = [];

		Object.keys(this.setters).forEach((setter, index) => {
			let df_prop = frappe.meta.docfield_map[this.doctype][setter];

			// Index + 1 to start filling from index 1
			// Since Search is a standrd field already pushed
			columns[(index + 1) % 3].push({
				fieldtype: df_prop.fieldtype,
				label: df_prop.label,
				fieldname: setter,
				options: df_prop.options,
				default: this.setters[setter]
			});
		});

		// https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object/seal
		if (Object.seal) {
			Object.seal(columns);
			// now a is a fixed-size array with mutable entries
		}

		fields = [
			...columns[0],
			{ fieldtype: "Column Break" },
			...columns[1],
			{ fieldtype: "Column Break" },
			...columns[2],
			{ fieldtype: "Section Break", fieldname: "primary_filters_sb" }
		];

		return fields;
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
		//get first three setters excluding search
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
		this.$results_area.empty();

		if (results && results.values.length) {
			this.render_card_view(results);
		} else {
			$('<p style="text-align: center;"><br><span class="text-muted">' + __("No Results") + '</span>'
				+ (frappe.model.can_create(this.doctype) ?
					('<br><br><a class="new-doc btn btn-default btn-sm">'
						+ __('Create a new {0}', [__(this.doctype)]) + "</a>") : '')
				+ '</p>').appendTo(this.$results_area).find(".new-doc").click(function () {
					frappe.new_doc(this.doctype);
			});
		}
	}

	render_card_view (results) {
		var me = this;
		this.$results_area.append(`<div class="grid-container"></div>`);

		var wrapper = this.$results_area.find(".grid-container")

		let card_fields = Object.keys(this.setters).slice(0,2);
		let columns = ["name", ...card_fields]

		$.each(results.values, function (i, v) {
			$(`<div class="grid-item">
				${me.get_image_html(v["image"], v["name"])}
				<div style="text-align: left;">
					<div class= "card-content">${frappe.ellipsis(v["name"], 20)}</div>
					<div class="card-content-muted">${frappe.ellipsis(v[columns[1]], 18)}</div>
					<div class="card-content-muted">${frappe.ellipsis(v[columns[2]], 18)}</div>
				</div>
				</div>`).appendTo(wrapper);
		})
	}

	get_image_html (image, name) {
		if (image) {
			return `<img class= "thumb" src=${image} alt=${name} title=${name}>
				</img>`
		} else {
			return `<div class="thumb" style="background-color: #fafbfc;">
				<span style="color:#d1d8dd; font-size:48px; margin-top: 20px;">${frappe.get_abbr(name)}</span>
				</div>`
		}

	}
};

// frappe.link_search = function (doctype, args, callback, btn) {

// }

//<div class="row link-select-row">\
/* <div class="col-xs-4">\
<b><a href="#">%(name)s</a></b></div>\
<div class="col-xs-8">\
<span class="text-muted">%(values)s</span></div>\
</div> */


// row.find("a")
// 	.attr('data-value', v[0])
// 	.click(function () {
// 		var value = $(this).attr("data-value");
// 		var $link = this;
// 		if (me.target.is_grid) {
// 			// set in grid
// 			me.set_in_grid(value);
// 		} else {
// 			if (me.target.doctype)
// 				me.target.parse_validate_and_set_in_model(value);
// 			else {
// 				me.target.set_input(value);
// 				me.target.$input.trigger("change");
// 			}
// 			me.dialog.hide();
// 		}
// 		return false;
// 	})


// set_in_grid: function (value) {
	// 	var me = this, updated = false;
	// 	var d = null;
	// 	if (this.qty_fieldname) {
	// 		frappe.prompt({
	// 			fieldname: "qty", fieldtype: "Float", label: "Qty",
	// 			"default": 1, reqd: 1
	// 		}, function (data) {
	// 			$.each(me.target.frm.doc[me.target.df.fieldname] || [], function (i, d) {
	// 				if (d[me.fieldname] === value) {
	// 					frappe.model.set_value(d.doctype, d.name, me.qty_fieldname, data.qty);
	// 					frappe.show_alert(__("Added {0} ({1})", [value, d[me.qty_fieldname]]));
	// 					updated = true;
	// 					return false;
	// 				}
	// 			});
	// 			if (!updated) {
	// 				frappe.run_serially([
	// 					() => {
	// 						d = me.target.add_new_row();
	// 					},
	// 					() => frappe.timeout(0.1),
	// 					() => frappe.model.set_value(d.doctype, d.name, me.fieldname, value),
	// 					() => frappe.timeout(0.5),
	// 					() => frappe.model.set_value(d.doctype, d.name, me.qty_fieldname, data.qty),
	// 					() => frappe.show_alert(__("Added {0} ({1})", [value, data.qty]))
	// 				]);
	// 			}
	// 		}, __("Set Quantity"), __("Set"));
	// 	} else if (me.dynamic_link_field) {
	// 		var d = me.target.add_new_row();
	// 		frappe.model.set_value(d.doctype, d.name, me.dynamic_link_field, me.dynamic_link_reference);
	// 		frappe.model.set_value(d.doctype, d.name, me.fieldname, value);
	// 		frappe.show_alert(__("{0} {1} added", [me.dynamic_link_reference, value]));
	// 	} else {
	// 		var d = me.target.add_new_row();
	// 		frappe.model.set_value(d.doctype, d.name, me.fieldname, value);
	// 		frappe.show_alert(__("{0} added", [value]));
	// 	}
	// }

		// if (r.values.length < 20) {
			// 	var more_btn = me.dialog.fields_dict.more.$wrapper;
			// 	more_btn.hide();
			// }

	// if (this.target.set_custom_query) {
		// 	this.target.set_custom_query(args);
		// }

		// // load custom query from grid
		// if (this.target.is_grid && this.target.fieldinfo[this.fieldname]
		// 	&& this.target.fieldinfo[this.fieldname].get_query) {
		// 	$.extend(args,
		// 		this.target.fieldinfo[this.fieldname].get_query(cur_frm.doc));
		// }
