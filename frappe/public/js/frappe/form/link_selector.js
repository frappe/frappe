// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.LinkSelector = class LinkSelector {
	constructor(opts) {
		/* help: Options: doctype, get_query, target */
		$.extend(this, opts);

		var me = this;
		if (this.doctype != "[Select]") {
			frappe.model.with_doctype(this.doctype, function (r) {
				me.make();
			});
		} else {
			this.make();
		}
	}
	make() {
		var me = this;

		this.start = 0;
		this.dialog = new frappe.ui.Dialog({
			title: __("Select {0}", [this.doctype == "[Select]" ? __("value") : __(this.doctype)]),
			fields: [
				{
					fieldtype: "Data",
					fieldname: "txt",
					label: __("Beginning with"),
					description: __("You can use wildcard %"),
				},
				{
					fieldtype: "HTML",
					fieldname: "results",
				},
				{
					fieldtype: "Button",
					fieldname: "more",
					label: __("More"),
					click: () => {
						me.start += 20;
						me.search();
					},
				},
			],
			primary_action_label: __("Search"),
			primary_action: function () {
				me.start = 0;
				me.search();
			},
		});

		if (this.txt) this.dialog.fields_dict.txt.set_input(this.txt);

		this.dialog.get_input("txt").on("keypress", function (e) {
			if (e.which === 13) {
				me.start = 0;
				me.search();
			}
		});
		this.dialog.show();
		this.search();
	}
	search() {
		var args = {
			txt: this.dialog.fields_dict.txt.get_value(),
			searchfield: "name",
			start: this.start,
		};
		var me = this;

		if (this.target.set_custom_query) {
			this.target.set_custom_query(args);
		}

		// load custom query from grid
		if (
			this.target.is_grid &&
			this.target.fieldinfo[this.fieldname] &&
			this.target.fieldinfo[this.fieldname].get_query
		) {
			$.extend(args, this.target.fieldinfo[this.fieldname].get_query(cur_frm.doc));
		}

		frappe.link_search(
			this.doctype,
			args,
			function (r) {
				var parent = me.dialog.fields_dict.results.$wrapper;
				if (args.start === 0) {
					parent.empty();
				}

				if (r.values.length) {
					$.each(r.values, function (i, v) {
						var row = $(
							repl(
								'<div class="row link-select-row">\
						<div class="col-xs-4">\
							<b><a href="#">%(name)s</a></b></div>\
						<div class="col-xs-8">\
							<span class="text-muted">%(values)s</span></div>\
						</div>',
								{
									name: v[0],
									values: v.splice(1).join(", "),
								}
							)
						).appendTo(parent);

						row.find("a")
							.attr("data-value", v[0])
							.click(function () {
								var value = $(this).attr("data-value");
								if (me.target.is_grid) {
									// set in grid
									// call search after value is set to get latest filtered results
									me.set_in_grid(value).then(() => me.search());
								} else {
									if (me.target.doctype)
										me.target.parse_validate_and_set_in_model(value);
									else {
										me.target.set_input(value);
										me.target.$input.trigger("change");
									}
									me.dialog.hide();
								}
								return false;
							});
					});
				} else {
					$(
						'<p><br><span class="text-muted">' +
							__("No Results") +
							"</span>" +
							(frappe.model.can_create(me.doctype)
								? '<br><br><a class="new-doc btn btn-default btn-sm">' +
								  __("Create a new {0}", [__(me.doctype)]) +
								  "</a>"
								: "") +
							"</p>"
					)
						.appendTo(parent)
						.find(".new-doc")
						.click(function () {
							frappe.new_doc(me.doctype);
						});
				}

				if (r.values.length < 20) {
					var more_btn = me.dialog.fields_dict.more.$wrapper;
					more_btn.hide();
				}
			},
			this.dialog.get_primary_btn()
		);
	}
	set_in_grid(value) {
		return new Promise((resolve) => {
			if (this.qty_fieldname) {
				frappe.prompt(
					{
						fieldname: "qty",
						fieldtype: "Float",
						label: "Qty",
						default: 1,
						reqd: 1,
					},
					(data) => {
						let updated = (this.target.frm.doc[this.target.df.fieldname] || []).some(
							(d) => {
								if (d[this.fieldname] === value) {
									frappe.model
										.set_value(d.doctype, d.name, this.qty_fieldname, data.qty)
										.then(() => {
											frappe.show_alert(
												__("Added {0} ({1})", [
													value,
													d[this.qty_fieldname],
												])
											);
											resolve();
										});
									return true;
								}
							}
						);
						if (!updated) {
							let d = null;
							frappe.run_serially([
								() => (d = this.target.add_new_row()),
								() => frappe.timeout(0.1),
								() => {
									let args = {};
									args[this.fieldname] = value;
									args[this.qty_fieldname] = data.qty;
									return frappe.model.set_value(d.doctype, d.name, args);
								},
								() => frappe.show_alert(__("Added {0} ({1})", [value, data.qty])),
								() => resolve(),
							]);
						}
					},
					__("Set Quantity"),
					__("Set Quantity")
				);
			} else if (this.dynamic_link_field) {
				let d = this.target.add_new_row();
				frappe.model.set_value(
					d.doctype,
					d.name,
					this.dynamic_link_field,
					this.dynamic_link_reference
				);
				frappe.model.set_value(d.doctype, d.name, this.fieldname, value).then(() => {
					frappe.show_alert(__("{0} {1} added", [this.dynamic_link_reference, value]));
					resolve();
				});
			} else {
				let d = this.target.add_new_row();
				frappe.model.set_value(d.doctype, d.name, this.fieldname, value).then(() => {
					frappe.show_alert(__("{0} added", [value]));
					resolve();
				});
			}
		});
	}
};

frappe.link_search = function (doctype, args, callback, btn) {
	if (!args) {
		args = {
			txt: "",
		};
	}
	args.doctype = doctype;
	if (!args.searchfield) {
		args.searchfield = "name";
	}

	frappe.call({
		method: "frappe.desk.search.search_widget",
		type: "GET",
		args: args,
		callback: function (r) {
			callback && callback(r);
		},
		btn: btn,
	});
};
