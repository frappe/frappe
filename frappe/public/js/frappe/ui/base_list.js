// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// new re-re-factored Listing object
// now called BaseList
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

frappe.ui.BaseList = Class.extend({
	init: function (opts) {
		this.opts = opts || {};
		this.set_defaults();
		if (opts) {
			this.make();
		}
	},
	set_defaults: function () {
		this.page_length = 20;
		this.start = 0;
		this.data = [];
	},
	make: function (opts) {
		if (opts) {
			this.opts = opts;
		}
		this.prepare_opts();

		$.extend(this, this.opts);

		// make dom
		this.wrapper = $(frappe.render_template('listing', this.opts));
		this.parent.append(this.wrapper);

		this.set_events();

		if (this.page) {
			this.wrapper.find('.list-toolbar-wrapper').hide();
		}

		if (this.show_filters) {
			this.make_filters();
		}
	},
	prepare_opts: function () {
		if (this.opts.new_doctype) {
			if (!frappe.boot.user.can_create.includes(this.opts.new_doctype)) {
				this.opts.new_doctype = null;
			}
		}
		if (!this.opts.no_result_message) {
			this.opts.no_result_message = __('Nothing to show');
		}
		if (!this.opts.page_length) {
			this.opts.page_length = this.user_settings && this.user_settings.limit || 20;
		}
		this.opts._more = __('More');
	},
	add_button: function (label, click, icon) {
		if (this.page) {
			return this.page.add_menu_item(label, click, icon)
		} else {
			this.wrapper.find('.list-toolbar-wrapper').removeClass('hide');
			return $('<button class="btn btn-default"></button>')
				.appendTo(this.wrapper.find('.list-toolbar'))
				.html((icon ? ('<i class="' + icon + '"></i> ') : '') + label)
				.click(click);
		}
	},
	set_events: function () {
		var me = this;

		// next page
		this.wrapper.find('.btn-more').click(function () {
			me.run(true);
		});

		this.wrapper.find(".btn-group-paging").on('click', '.btn', function () {
			me.page_length = cint($(this).attr("data-value"));

			me.wrapper.find(".btn-group-paging .btn-info").removeClass("btn-info");
			$(this).addClass("btn-info");

			// always reset when changing list page length
			me.run();
		});

		// select the correct page length
		if (this.opts.page_length !== 20) {
			this.wrapper.find(".btn-group-paging .btn-info").removeClass("btn-info");
			this.wrapper
				.find(".btn-group-paging .btn[data-value='" + this.opts.page_length + "']")
				.addClass('btn-info');
		}

		// title
		if (this.title) {
			this.wrapper.find('h3').html(this.title).show();
		}

		// new
		this.set_primary_action();

		if (me.no_toolbar || me.hide_toolbar) {
			me.wrapper.find('.list-toolbar-wrapper').hide();
		}
	},

	set_primary_action: function () {
		var me = this;
		if (this.new_doctype) {
			this.page.set_primary_action(
				__("New"),
				me.make_new_doc.bind(me, me.new_doctype),
				"octicon octicon-plus"
			);
		} else {
			this.page.clear_primary_action();
		}
	},

	make_new_doc: function (doctype) {
		var me = this;
		frappe.model.with_doctype(doctype, function () {
			if (me.custom_new_doc) {
				me.custom_new_doc(doctype);
			} else {
				if (me.filter_list) {
					frappe.route_options = {};
					me.filter_list.get_filters().forEach(function (f, i) {
						if (f[2] === "=" && !frappe.model.std_fields_list.includes(f[1])) {
							frappe.route_options[f[1]] = f[3];
						}
					});
				}
				frappe.new_doc(doctype, true);
			}
		});
	},

	make_filters: function () {
		this.make_standard_filters();

		this.filter_list = new frappe.ui.FilterList({
			base_list: this,
			parent: this.wrapper.find('.list-filters').show(),
			doctype: this.doctype,
			filter_fields: this.filter_fields,
			default_filters: this.default_filters || []
		});
		// default filter for submittable doctype
		if (frappe.model.is_submittable(this.doctype)) {
			this.filter_list.add_filter(this.doctype, "docstatus", "!=", 2);
		}
	},

	make_standard_filters: function() {
		var me = this;
		if (this.standard_filters_added) {
			return;
		}

		if (this.meta) {
			var filter_count = 1;
			if(this.is_list_view) {
				$(`<span class="octicon octicon-search text-muted small"></span>`)
					.prependTo(this.page.page_form);
			}
			this.page.add_field({
				fieldtype: 'Data',
				label: 'ID',
				condition: 'like',
				fieldname: 'name',
				onchange: () => { me.refresh(true); }
			});

			this.meta.fields.forEach(function(df, i) {
				if(df.in_standard_filter && !frappe.model.no_value_type.includes(df.fieldtype)) {
					let options = df.options;
					let condition = '=';
					let fieldtype = df.fieldtype;
					if (['Text', 'Small Text', 'Text Editor', 'Data'].includes(fieldtype)) {
						fieldtype = 'Data';
						condition = 'like';
					}

					if (df.fieldtype === "Select" && df.options) {
						options = df.options.split("\n");
						if(options.length > 0 && options[0] != "") {
							options.unshift("");
							options = options.join("\n");
						}
					}

					if (df.fieldtype === 'Data' && df.options) {
						// don't format email / number in filters
						options = '';
					}

					let f = me.page.add_field({
						fieldtype: fieldtype,
						label: __(df.label),
						options: options,
						fieldname: df.fieldname,
						condition: condition,
						onchange: () => {me.refresh(true);}
					});
					filter_count ++;
					if (filter_count > 3) {
						$(f.wrapper).addClass('hidden-sm').addClass('hidden-xs');
					}
					if (filter_count > 5) {
						return false;
					}
				}
			});
		}

		this.standard_filters_added = true;
	},

	update_standard_filters: function(filters) {
		let me = this;
		for(let key in this.page.fields_dict) {
			let field = this.page.fields_dict[key];
			let value = field.get_value();
			if (value) {
				if (field.df.condition==='like' && !value.includes('%')) {
					value = '%' + value + '%';
				}
				filters.push([
					me.doctype,
					field.df.fieldname,
					field.df.condition || '=',
					value
				]);
			}
		}
	},


	clear: function () {
		this.data = [];
		this.wrapper.find('.list-select-all').prop('checked', false);
		this.wrapper.find('.result-list').empty();
		this.wrapper.find('.result').show();
		this.wrapper.find('.no-result').hide();
		this.start = 0;
		this.onreset && this.onreset();
	},

	set_filters_from_route_options: function ({clear_filters=true} = {}) {
		var me = this;
		if(this.filter_list && clear_filters) {
			this.filter_list.clear_filters();
		}

		for(var field in frappe.route_options) {
			var value = frappe.route_options[field];
			var doctype = null;

			// if `Child DocType.fieldname`
			if (field.includes(".")) {
				doctype = field.split(".")[0];
				field = field.split(".")[1];
			}

			// find the table in which the key exists
			// for example the filter could be {"item_code": "X"}
			// where item_code is in the child table.

			// we can search all tables for mapping the doctype
			if (!doctype) {
				doctype = frappe.meta.get_doctype_for_field(me.doctype, field);
			}

			if (doctype && me.filter_list) {
				if ($.isArray(value)) {
					me.filter_list.add_filter(doctype, field, value[0], value[1]);
				} else {
					me.filter_list.add_filter(doctype, field, "=", value);
				}
			}
		}
		frappe.route_options = null;
	},

	run: function(more) {
		setTimeout(() => this._run(more), 100);
	},

	_run: function (more) {
		var me = this;
		if (!more) {
			this.start = 0;
			this.onreset && this.onreset();
		}

		var args = this.get_call_args();
		this.save_user_settings_locally(args);

		// user_settings are saved by db_query.py when dirty
		$.extend(args, {
			user_settings: frappe.model.user_settings[this.doctype]
		});

		return frappe.call({
			method: this.opts.method || 'frappe.desk.query_builder.runquery',
			freeze: this.opts.freeze !== undefined ? this.opts.freeze : true,
			args: args,
			callback: function (r) {
				me.dirty = false;
				me.render_results(r);
			},
			no_spinner: this.opts.no_loading
		});
	},
	save_user_settings_locally: function (args) {
		if (this.opts.save_user_settings && this.doctype && !this.docname) {
			// save list settings locally
			var user_settings = frappe.model.user_settings[this.doctype];
			var different = false;

			if (!user_settings) {
				return;
			}

			if (!frappe.utils.arrays_equal(args.filters, user_settings.filters)) {
				// settings are dirty if filters change
				user_settings.filters = args.filters;
				different = true;
			}

			if (user_settings.order_by !== args.order_by) {
				user_settings.order_by = args.order_by;
				different = true;
			}

			if (user_settings.limit !== args.limit_page_length) {
				user_settings.limit = args.limit_page_length || 20
				different = true;
			}

			// save fields in list settings
			if (args.save_user_settings_fields) {
				user_settings.fields = args.fields;
			}

			if (different) {
				user_settings.updated_on = moment().toString();
			}
		}
	},
	get_call_args: function () {
		// load query
		if (!this.method) {
			var query = this.get_query && this.get_query() || this.query;
			query = this.add_limits(query);
			var args = {
				query_max: this.query_max,
				as_dict: 1
			}
			args.simple_query = query;
		} else {
			var args = {
				start: this.start,
				page_length: this.page_length
			}
		}

		// append user-defined arguments
		if (this.args)
			$.extend(args, this.args)

		if (this.get_args) {
			$.extend(args, this.get_args());
		}
		return args;
	},
	render_results: function (r) {
		if (this.start === 0)
			this.clear();

		this.wrapper.find('.btn-more, .list-loading').hide();

		var values = [];

		if (r.message) {
			values = this.get_values_from_response(r.message);
		}

		var show_results = true;
		if(this.show_no_result) {
			if($.isFunction(this.show_no_result)) {
				show_results = !this.show_no_result()
			} else {
				show_results = !this.show_no_result;
			}
		}

		// render result view when
		// length > 0 OR
		// explicitly set by flag
		if (values.length || show_results) {
			this.data = this.data.concat(values);
			this.render_view(values);
			this.update_paging(values);
		} else if (this.start === 0) {
			// show no result message
			this.wrapper.find('.result').hide();

			var msg = '';
			var no_result_message = this.no_result_message;
			if(no_result_message && $.isFunction(no_result_message)) {
				msg = no_result_message();
			} else if(typeof no_result_message === 'string') {
				msg = no_result_message;
			} else {
				msg = __('No Results')
			}

			this.wrapper.find('.no-result').html(msg).show();
		}

		this.wrapper.find('.list-paging-area')
			.toggle(values.length > 0|| this.start > 0);

		// callbacks
		if (this.onrun) this.onrun();
		if (this.callback) this.callback(r);
		this.wrapper.trigger("render-complete");
	},

	get_values_from_response: function (data) {
		// make dictionaries from keys and values
		if (data.keys && $.isArray(data.keys)) {
			return frappe.utils.dict(data.keys, data.values);
		} else {
			return data;
		}
	},

	render_view: function (values) {
		// override this method in derived class
	},

	update_paging: function (values) {
		if (values.length >= this.page_length) {
			this.wrapper.find('.btn-more').show();
			this.start += this.page_length;
		}
	},

	refresh: function () {
		this.run();
	},
	add_limits: function (query) {
		return query + ' LIMIT ' + this.start + ',' + (this.page_length + 1);
	},
	set_filter: function (fieldname, label, no_run, no_duplicate) {
		var filter = this.filter_list.get_filter(fieldname);
		if (filter) {
			var value = cstr(filter.field.get_value());
			if (value.includes(label)) {
				// already set
				return false

			} else if (no_duplicate) {
				filter.set_values(this.doctype, fieldname, "=", label);
			} else {
				// second filter set for this field
				if (fieldname == '_user_tags' || fieldname == "_liked_by") {
					// and for tags
					this.filter_list.add_filter(this.doctype, fieldname, 'like', '%' + label + '%');
				} else {
					// or for rest using "in"
					filter.set_values(this.doctype, fieldname, 'in', value + ', ' + label);
				}
			}
		} else {
			// no filter for this item,
			// setup one
			if (['_user_tags', '_comments', '_assign', '_liked_by'].includes(fieldname)) {
				this.filter_list.add_filter(this.doctype, fieldname, 'like', '%' + label + '%');
			} else {
				this.filter_list.add_filter(this.doctype, fieldname, '=', label);
			}
		}
		if (!no_run)
			this.run();
	},
	init_user_settings: function () {
		this.user_settings = frappe.model.user_settings[this.doctype] || {};
	},
	call_for_selected_items: function (method, args) {
		var me = this;
		args.names = this.get_checked_items().map(function (item) {
			return item.name;
		});

		frappe.call({
			method: method,
			args: args,
			freeze: true,
			callback: function (r) {
				if (!r.exc) {
					if (me.list_header) {
						me.list_header.find(".list-select-all").prop("checked", false);
					}
					me.refresh(true);
				}
			}
		});
	}
});
