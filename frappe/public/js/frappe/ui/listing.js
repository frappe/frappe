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
			this.opts.page_length = 20;
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
		this.$w = $(this.parent).find('.frappe-list');
		this.set_events();

		if(this.page) {
			this.$w.find('.list-toolbar-wrapper').toggle(false);
		}

		if(this.show_filters) {
			this.make_filters();
		}
	},
	add_button: function(label, click, icon) {
		if(this.page) {
			return this.page.add_menu_item(label, click, icon)
		} else {
			this.$w.find('.list-toolbar-wrapper').removeClass("hide");
			$button = $('<button class="btn btn-default"></button>')
				.appendTo(this.$w.find('.list-toolbar'))
				.html((icon ? ("<i class='"+icon+"'></i> ") : "") + label)
				.click(click);
			return $button
		}
	},
	set_events: function() {
		var me = this;

		// next page
		this.$w.find('.btn-more').click(function() {
			me.run({append: true });
		});

		this.$w.find(".btn-group-paging .btn").click(function() {
			me.page_length = cint($(this).attr("data-value"));
			me.$w.find(".btn-group-paging .btn-info").removeClass("btn-info");
			$(this).addClass("btn-info");
			me.run({append: true});
		});

		// title
		if(this.title) {
			this.$w.find('h3').html(this.title).toggle(true);
		}

		// new
		this.set_primary_action();

		if(me.no_toolbar || me.hide_toolbar) {
			me.$w.find('.list-toolbar-wrapper').toggle(false);
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
				var doc = frappe.model.get_new_doc(doctype);
				if(me.filter_list) {
					frappe.route_options = {};
					$.each(me.filter_list.get_filters(), function(i, f) {
						if(f[2]==="=" && !in_list(frappe.model.std_fields_list, f[1])) {
							frappe.route_options[f[1]] = f[3];
						}
					});
				}
				frappe.set_route("Form", doctype, doc.name);
			}
		});
	},

	make_filters: function() {
		this.filter_list = new frappe.ui.FilterList({
			listobj: this,
			$parent: this.$w.find('.list-filters').toggle(true),
			doctype: this.doctype,
			filter_fields: this.filter_fields
		});
		if(frappe.model.is_submittable(this.doctype)) {
			this.filter_list.add_filter(this.doctype, "docstatus", "!=", 2);
		};
	},

	clear: function() {
		this.data = [];
		this.$w.find('.result-list').empty();
		this.$w.find('.result').toggle(true);
		this.$w.find('.no-result').toggle(false);
		this.start = 0;
	},
	run: function(more) {
		var me = this;
		if(!more) {
			this.start = 0;
			if(this.onreset) this.onreset();
		}

		if(!me.opts.no_loading)
			me.set_working(true);

		return frappe.call({
			method: this.opts.method || 'frappe.desk.query_builder.runquery',
			type: "GET",
			freeze: (this.opts.freeze != undefined ? this.opts.freeze : true),
			args: this.get_call_args(),
			callback: function(r) {
				if(!me.opts.no_loading)
					me.set_working(false);
				me.dirty = false;
				me.render_results(r);
			},
			no_spinner: this.opts.no_loading
		});
	},
	set_working: function(flag) {
		this.$w.find('.img-load').toggle(flag);
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

		this.$w.find('.list-paging-area, .list-loading').toggle(false);

		if(r.message) {
			r.values = this.get_values_from_response(r.message);
		}

		if(r.values && r.values.length) {
			this.data = this.data.concat(r.values);
			this.render_list(r.values);
			this.update_paging(r.values);
		} else {
			if(this.start===0) {
				this.$w.find('.result').toggle(false);

				var msg = this.get_no_result_message
					? this.get_no_result_message()
					: (this.no_result_message
						? this.no_result_message
						: __("Nothing to show"));

				this.$w.find('.no-result')
					.html(msg)
					.toggle(true);
			}
		}

		// callbacks
		if(this.onrun) this.onrun();
		if(this.callback) this.callback(r);
		this.$w.trigger("render-complete");
	},

	get_values_from_response: function(data) {
		// make dictionaries from keys and values
		if(data.keys && $.isArray(data.keys)) {
			return frappe.utils.dict(data.keys, data.values);
		} else {
			return data;
		}
	},

	render_list: function(values) {
		var m = Math.min(values.length, this.page_length);
		this.last_page = values;
		if(this.filter_list) {
			this.filter_values = this.filter_list.get_filters();
		}

		// render the rows
		for(var i=0; i < m; i++) {
			this.render_row(this.add_row(values[i]), values[i], this, i);
		}
	},
	update_paging: function(values) {
		if(values.length >= this.page_length) {
			this.$w.find('.list-paging-area').toggle(true);
			this.start += this.page_length;
		}
	},
	add_row: function(row) {
		return $('<div class="list-row">')
			.data("data", row)
			.appendTo(this.$w.find('.result-list'))
			.get(0);
	},
	refresh: function() {
		this.run();
	},
	add_limits: function(query) {
		query += ' LIMIT ' + this.start + ',' + (this.page_length+1);
		return query
	},
	set_filter: function(fieldname, label, doctype) {
		if(!doctype) doctype = this.doctype;
		var filter = this.filter_list.get_filter(fieldname);
		if(filter) {
			var v = filter.field.get_parsed_value();
			if(v.indexOf(label)!=-1) {
				// already set
				return this;
			} else {
				// second filter set for this field
				if(fieldname=='_user_tags') {
					// and for tags
					this.filter_list.add_filter(doctype, fieldname,
						'like', '%' + label + '%');
				} else {
					// or for rest using "in"
					filter.set_values(doctype, fieldname, 'in', v + ', ' + label);
				}
			}
		} else {
			// no filter for this item,
			// setup one
			if(['_user_tags', '_comments', '_assign', '_starred_by'].indexOf(fieldname)!==-1) {
				this.filter_list.add_filter(doctype, fieldname,
					'like', '%' + label + '%');
			} else {
				this.filter_list.add_filter(doctype, fieldname, '=', label);
			}
		}
		return this;
	}
});
