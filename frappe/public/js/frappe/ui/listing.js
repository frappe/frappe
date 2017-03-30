// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// new re-factored Listing object
// removed rarely used functionality
//
// opts:
//   parent

//   method (method to call on server)
//   args (additional args to method)
//   get_args (method to return args as dict)

//   show_filters [false]
//   doctype
//   filter_fields (if given, this list is rendered, else built from doctype)

//   query or get_query (will be deprecated)
//   query_max
//   buttons_in_frame

//   no_result_message ("No result")

//   page_length (20)
//   hide_refresh (False)
//   no_toolbar
//   new_doctype
//   [function] render_row(parent, data)
//   [function] onrun
//   no_loading (no ajax indicator)

frappe.provide('frappe.ui');
frappe.ui.Listing = Class.extend({
	init: function(opts) {
		this.opts = opts || {};
		this.page_length = 20;
		this.start = 0;
		this.data = [];
		if(opts) {
			this.make();
		}
	},
	prepare_opts: function() {
		if(this.opts.new_doctype) {
			if(frappe.boot.user.can_create.indexOf(this.opts.new_doctype)==-1) {
				this.opts.new_doctype = null;
			} else {
				this.opts.new_doctype = this.opts.new_doctype;
			}
		}
		if(!this.opts.no_result_message) {
			this.opts.no_result_message = __('Nothing to show');
		}
		if(!this.opts.page_length) {
			this.opts.page_length = this.list_settings ? (this.list_settings.limit || 20) : 20;
		}
		this.opts._more = __("More");
	},
	make: function(opts) {
		if(opts) {
			this.opts = opts;
		}
		this.prepare_opts();
		$.extend(this, this.opts);

		$(this.parent).html(frappe.render_template("listing", this.opts));
		this.wrapper = $(this.parent).find('.frappe-list');
		this.set_events();

		if(this.page) {
			this.wrapper.find('.list-toolbar-wrapper').toggle(false);
		}

		if(this.show_filters) {
			this.make_filters();
		}
	},
	add_button: function(label, click, icon) {
		if(this.page) {
			return this.page.add_menu_item(label, click, icon)
		} else {
			this.wrapper.find('.list-toolbar-wrapper').removeClass("hide");
			$button = $('<button class="btn btn-default"></button>')
				.appendTo(this.wrapper.find('.list-toolbar'))
				.html((icon ? ("<i class='"+icon+"'></i> ") : "") + label)
				.click(click);
			return $button
		}
	},
	set_events: function() {
		var me = this;

		// next page
		this.wrapper.find('.btn-more').click(function() {
			me.run(true);
		});

		this.wrapper.find(".btn-group-paging .btn").click(function() {
			me.page_length = cint($(this).attr("data-value"));
			me.wrapper.find(".btn-group-paging .btn-info").removeClass("btn-info");
			$(this).addClass("btn-info");

			// always reset when changing list page length
			me.run();
		});

		// select the correct page length
		if(this.opts.page_length != 20) {
			this.wrapper.find(".btn-group-paging .btn-info").removeClass("btn-info");
			this.wrapper.find(".btn-group-paging .btn[data-value='"+ this.opts.page_length +"']").addClass('btn-info');
		}

		// title
		if(this.title) {
			this.wrapper.find('h3').html(this.title).toggle(true);
		}

		// new
		this.set_primary_action();

		if(me.no_toolbar || me.hide_toolbar) {
			me.wrapper.find('.list-toolbar-wrapper').toggle(false);
		}
	},

	set_primary_action: function() {
		var me = this;
		if(this.new_doctype) {
			if(this.listview.settings.set_primary_action){
				this.listview.settings.set_primary_action(this);
			} else {
				this.page.set_primary_action(__("New"), function() {
					me.make_new_doc(me.new_doctype); }, "octicon octicon-plus");
			}
		} else {
			this.page.clear_primary_action();
		}
	},

	make_new_doc: function(doctype) {
		var me = this;
		frappe.model.with_doctype(doctype, function() {
			if(me.custom_new_doc) {
				me.custom_new_doc(doctype);
			} else {
				if(me.filter_list) {
					frappe.route_options = {};
					$.each(me.filter_list.get_filters(), function(i, f) {
						if(f[2]==="=" && !in_list(frappe.model.std_fields_list, f[1])) {
							frappe.route_options[f[1]] = f[3];
						}
					});
				}
				frappe.new_doc(doctype, true);
			}
		});
	},

	make_filters: function() {
		this.filter_list = new frappe.ui.FilterList({
			listobj: this,
			$parent: this.wrapper.find('.list-filters').toggle(true),
			doctype: this.doctype,
			filter_fields: this.filter_fields,
			default_filters:this.default_filters? this.default_filters: this.listview?this.listview.settings.default_filters:[]
		});
		if(frappe.model.is_submittable(this.doctype)) {
			this.filter_list.add_filter(this.doctype, "docstatus", "!=", 2);
		};
	},

	clear: function() {
		this.data = [];
		this.wrapper.find('.result-list').empty();
		this.wrapper.find('.result').toggle(true);
		this.wrapper.find('.no-result').toggle(false);
		this.start = 0;
		if(this.onreset) this.onreset();
	},

	set_filters_from_route_options: function() {
		var me = this;
		this.filter_list.clear_filters();
		$.each(frappe.route_options, function(key, value) {
			var doctype = null;

			// if `Child DocType.fieldname`
			if (key.indexOf(".")!==-1) {
				doctype = key.split(".")[0];
				key = key.split(".")[1];
			}

			// find the table in which the key exists
			// for example the filter could be {"item_code": "X"}
			// where item_code is in the child table.

			// we can search all tables for mapping the doctype
			if(!doctype) {
				doctype = frappe.meta.get_doctype_for_field(me.doctype, key);
			}

			if(doctype) {
				if($.isArray(value)) {
					me.filter_list.add_filter(doctype, key, value[0], value[1]);
				} else {
					me.filter_list.add_filter(doctype, key, "=", value);
				}
			}
		});
		frappe.route_options = null;
	},

	run: function(more) {
		var me = this;
		if(!more) {
			this.start = 0;
			if(this.onreset) this.onreset();
		}

		if(!me.opts.no_loading) {
			me.set_working(true);
		}

		var args = this.get_call_args();
		this.save_list_settings_locally(args);

		// list_settings are saved by db_query.py when dirty
		$.extend(args, {
			list_settings: frappe.model.list_settings[this.doctype]
		});

		return frappe.call({
			method: this.opts.method || 'frappe.desk.query_builder.runquery',
			type: "GET",
			freeze: (this.opts.freeze != undefined ? this.opts.freeze : true),
			args: args,
			callback: function(r) {
				if(!me.opts.no_loading)
					me.set_working(false);
				me.dirty = false;
				me.render_results(r);
			},
			no_spinner: this.opts.no_loading
		});
	},
	save_list_settings_locally: function(args) {
		if(this.opts.save_list_settings && this.doctype && !this.docname) {
			// save list settings locally
			list_settings = frappe.model.list_settings[this.doctype];

			if(!list_settings) {
				return
			}

			var different = false;

			if(!frappe.utils.arrays_equal(args.filters, list_settings.filters)) {
				//dont save filters in Kanban view
				if(this.current_view!=="Kanban") {
					// settings are dirty if filters change
					list_settings.filters = args.filters || [];
					different = true;
				}
			}

			if(list_settings.order_by !== args.order_by) {
				list_settings.order_by = args.order_by;
				different = true;
			}

			if(list_settings.limit != args.limit_page_length) {
				list_settings.limit = args.limit_page_length || 20
				different = true;
			}

			// save fields in list settings
			if(args.save_list_settings_fields) {
				list_settings.fields = args.fields;
			}

			if(different) {
				list_settings.updated_on = moment().toString();
			}
		}
	},
	set_working: function(flag) {
		this.wrapper.find('.img-load').toggle(flag);
	},
	get_call_args: function() {
		// load query
		if(!this.method) {
			var query = this.get_query ? this.get_query() : this.query;
			query = this.add_limits(query);
			var args={
				query_max: this.query_max,
				as_dict: 1
			}
			args.simple_query = query;
		} else {
			var args = {
				limit_start: this.start,
				limit_page_length: this.page_length
			}
		}

		// append user-defined arguments
		if(this.args)
			$.extend(args, this.args)

		if(this.get_args) {
			$.extend(args, this.get_args());
		}
		return args;
	},
	render_results: function(r) {
		if(this.start===0) this.clear();

		this.wrapper.find('.btn-more, .list-loading').toggle(false);

		r.values = [];

		if(r.message) {
			r.values = this.get_values_from_response(r.message);
		}

		if(r.values.length || this.force_render_view) {
			if (this.data.length && this.data[this.data.length - 1]._totals_row) {
				this.data.pop();
			}
			this.data = this.data.concat(r.values);
			this.render_view(r.values);
			// this.render_list(r.values);
			this.update_paging(r.values);
		} else {
			if(this.start===0) {
				this.wrapper.find('.result').toggle(false);

				var msg = this.get_no_result_message
					? this.get_no_result_message()
					: (this.no_result_message
						? this.no_result_message
						: __("No Result"));

				this.wrapper.find('.no-result')
					.html(msg)
					.toggle(true);
			}
		}

		this.wrapper.find('.list-paging-area').toggle((r.values.length || this.start > 0) ? true : false);

		// callbacks
		if(this.onrun) this.onrun();
		if(this.callback) this.callback(r);
		this.wrapper.trigger("render-complete");
	},

	get_values_from_response: function(data) {
		// make dictionaries from keys and values
		if(data.keys && $.isArray(data.keys)) {
			return frappe.utils.dict(data.keys, data.values);
		} else {
			return data;
		}
	},

	render_view: function(values) {
		this.list_view = new frappe.views.ListView({
			doctype: this.doctype,
			values: values,
		});
	},

	render_list: function(values) {
		// TODO: where is this used?
		// this.last_page = values;
		// if(this.filter_list) {
		// 	// and this?
		// 	this.filter_values = this.filter_list.get_filters();
		// }

		this.render_rows(values);
	},
	render_rows: function(values) {
		// render the rows
		var m = Math.min(values.length, this.page_length);
		for(var i=0; i < m; i++) {
			this.render_row(this.add_row(values[i]), values[i], this, i);
		}
	},
	update_paging: function(values) {
		if(values.length >= this.page_length) {
			this.wrapper.find('.btn-more').toggle(true);
			this.start += this.page_length;
		}
	},
	add_row: function(row) {
		return $('<div class="list-row">')
			.data("data", (this.meta && this.meta.image_view) == 0 ? row : null)
			.appendTo(this.wrapper.find('.result-list'))
			.get(0);
	},
	refresh: function() {
		this.run();
	},
	add_limits: function(query) {
		query += ' LIMIT ' + this.start + ',' + (this.page_length+1);
		return query
	},
	set_filter: function(fieldname, label, no_run, no_duplicate, parent) {
		var filter = this.filter_list.get_filter(fieldname);
		doctype = parent && this.doctype != parent? parent: this.doctype

		if(filter) {
			var v = cstr(filter.field.get_parsed_value());
			if(v.indexOf(label)!=-1) {
				// already set
				return false

			} else if(no_duplicate) {
				filter.set_values(doctype, fieldname, "=", label);
			} else {
				// second filter set for this field
				if(fieldname=='_user_tags' || fieldname=="_liked_by")  {
					// and for tags
					this.filter_list.add_filter(doctype, fieldname, 'like', '%' + label + '%');
				} else {
					// or for rest using "in"
					filter.set_values(doctype, fieldname, 'in', v + ', ' + label);
				}
			}
		} else {
			// no filter for this item,
			// setup one
			if(['_user_tags', '_comments', '_assign', '_liked_by'].indexOf(fieldname)!==-1) {
				this.filter_list.add_filter(doctype, fieldname, 'like', '%' + label + '%');
			} else {
				this.filter_list.add_filter(doctype, fieldname, '=', label);
			}
		}
		if(!no_run)
			this.run();
	},
	init_list_settings: function() {
		if(frappe.model.list_settings[this.doctype]) {
			this.list_settings = frappe.model.list_settings[this.doctype];
		} else {
			this.list_settings = {};
		}
	},
	call_for_selected_items: function(method, args) {
		var me = this;
		args.names = $.map(this.get_checked_items(), function(d) { return d.name; });

		frappe.call({
			method: method,
			args: args,
			freeze: true,
			callback: function(r) {
				if(!r.exc) {
					if(me.list_header) {
						me.list_header.find(".list-select-all").prop("checked", false);
					}
					me.refresh();
				}
			}
		});
	}
});
