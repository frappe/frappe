// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.views.doclistview');
frappe.provide('frappe.listviews');

cur_list = null;
frappe.views.ListFactory = frappe.views.Factory.extend({
	make: function(route) {
		var me = this,
			doctype = route[1];
		frappe.model.with_doctype(doctype, function() {
			if(locals["DocType"][doctype].issingle) {
				frappe.set_re_route("Form", doctype);
			} else {
				new frappe.views.DocListView({
					doctype: doctype,
					page: me.make_page(true)
				});
				me.set_cur_list();
			}
		});
	},
	show: function() {
		this._super();
		this.set_cur_list();
	},
	set_cur_list: function() {
		cur_list = frappe.container.page && frappe.container.page.doclistview;
	}
});

$(document).on("save", function(event, doc) {
	var list_page = "List/" + doc.doctype;
	if(frappe.pages[list_page]) {
		if(frappe.pages[list_page].doclistview)
			frappe.pages[list_page].doclistview.dirty = true;
	}
})

frappe.views.DocListView = frappe.ui.Listing.extend({
	init: function(opts) {
		$.extend(this, opts)
		this.label = __(this.doctype);
		this.dirty = true;
		this.tags_shown = false;
		this.label = (this.label.toLowerCase().substr(-4) == 'list') ?
		 	__(this.label) : (__(this.label) + ' ' + __('List'));
		this.make_page();
		this.setup();

		var me = this;
		$(this.page).on("show", function() {
			me.refresh();
		});

		// refresh on init
		me.refresh();
	},

	make_page: function() {
		var me = this;
		this.page.doclistview = this;
		this.$page = $(this.page).css({"min-height": "400px"});

		$('<div class="frappe-list-area" style="margin-bottom: 25px;">\
			<div class="help">'+__('Loading')+'...</div></div>')
			.appendTo(this.$page.find(".layout-main-section"));

		this.$page.find(".layout-main-section")
			.addClass("listview-main-section");
		this.appframe = this.page.appframe;
		var module = locals.DocType[this.doctype].module;

		this.appframe.set_title(__("{0} List", [__(this.doctype)]));
		this.appframe.add_module_icon(module, this.doctype, null, true);
		this.appframe.set_title_left(function() {
			frappe.set_route(frappe.listview_parent_route[me.doctype]
				|| frappe.get_module(module).link);
		});
	},

	setup: function() {
		var me = this;
		this.can_delete = frappe.model.can_delete(this.doctype);
		this.meta = locals.DocType[this.doctype];
		this.$page.find('.frappe-list-area').empty(),
		this.setup_listview();
		this.init_list(false);
		this.init_stats();
		this.init_minbar();
		this.init_star();
		this.show_match_help();
		this.init_listview();
		this.setup_filterable();
		this.init_filters();
	},

	init_listview: function() {
		if(this.listview.settings.onload) {
			this.listview.settings.onload(this);
		}

		if(this.listview.settings.set_title_left) {
			this.appframe.set_title_left(this.listview.settings.set_title_left);
		} else if(this.listview.settings.parent_route) {
			this.appframe.set_title_left(function() {
				frappe.set_route(me.listview.settings.parent_route);
			});
		}
	},

	set_sidebar_height: function() {
		var h_main = this.$page.find(".layout-main-section").height();
		var h_side = this.$page.find(".layout-side-section").height();
		if(h_side > h_main)
			this.$page.find(".layout-main-section").css({"min-height": h_side});
	},

	setup_filterable: function() {
		var me = this;
		this.$page.on("click", ".filterable", function(e) {
			var filters = $(this).attr("data-filter").split("|");
			var added = false;
			$.each(filters, function(i, f) {
				f = f.split(",");
				if(f[2]==="Today") {
					f[2] = frappe.datetime.get_today();
				} else if(f[2]=="User") {
					f[2] = user;
				}
				added = added || me.filter_list.add_filter(me.doctype,
					f[0], f[1], f.slice(2).join(","));
			});
			added && me.run();
		})
	},

	init_filters: function() {
		var me = this;
		if(this.listview.settings.filters) {
			$.each(this.listview.settings.filters, function(i, f) {
				if(f.length===3) {
					f = [me.doctype, f[0], f[1], f[2]]
				}
				me.filter_list.add_filter(f[0], f[1], f[2], f[3]);
			});
		}
	},

	show_match_help: function() {
		var me = this;
		var match_rules_list = frappe.perm.get_match_rules(this.doctype);
		var perm = frappe.perm.get_perm(this.doctype);

		if(match_rules_list.length) {
			var or_match_text = [];

			$.each(match_rules_list, function(i, match_rules) {
				var match_text = []
				$.each(match_rules, function(key, values) {
					if(values.length==0) {
						match_text.push(__(key) + __(" is not set"));
					} else if(values.length) {
						match_text.push(__(key) + " = " + frappe.utils.comma_or(values));
					}
				});

				if (match_text.length) {
					var txt = "<ul>" + $.map(match_text, function(txt) { return "<li>"+txt+"</li>" }).join("") + "</ul>";
					or_match_text.push(txt);
				}
			});

			if (or_match_text.length) {
				frappe.utils.set_footnote(this, this.$page.find(".layout-main-section"),
					"<p style=\"margin-bottom: 7px;\">"
						+ __("Additional filters based on User Permissions, having:") + "</p>"
					+ or_match_text.join("<p class=\"strong\" \
						style=\"margin-left: 40px; margin-top: 7px; margin-bottom: 7px;\">"
						+ __("or") + "</p>")
					+ "<p class=\"text-muted\" style=\"margin-top: 15px;\">"
					+ __("Note: fields having empty value for above criteria are not filtered out.")
					+ "</p>");
				$(this.footnote_area).css({"margin-top":"0px", "margin-bottom":"20px"});
			}
		}
	},
	setup_listview: function() {
		this.listview = frappe.views.get_listview(this.doctype, this);
		this.wrapper = this.$page.find('.frappe-list-area');
		this.page_length = 20;
		this.allow_delete = true;
	},
	init_list: function(auto_run) {
		var me = this;
		// init list
		this.make({
			method: 'frappe.desk.reportview.get',
			get_args: this.get_args,
			parent: this.wrapper,
			freeze: true,
			start: 0,
			page_length: this.page_length,
			show_filters: true,
			show_grid: true,
			new_doctype: this.doctype,
			allow_delete: this.allow_delete,
			no_result_message: this.make_no_result(),
			custom_new_doc: me.listview.make_new_doc || undefined,
		});

		// make_new_doc can be overridden so that default values can be prefilled
		// for example - communication list in customer
		$(this.wrapper).on("click", 'button[list_view_doc="'+me.doctype+'"]', function(){
			(me.listview.make_new_doc || me.make_new_doc).apply(me, [me.doctype]);
		});

		if((auto_run !== false) && (auto_run !== 0))
			this.refresh();
	},

	refresh: function() {
		var me = this;
		if(frappe.route_options) {
			me.set_route_options();
		} else if(me.dirty) {
			me.run();
		} else {
			if(new Date() - (me.last_updated_on || 0) > 30000) {
				// older than 5 mins, refresh
				me.run();
			}
		}
	},

	set_route_options: function() {
		var me = this;
		me.filter_list.clear_filters();
		$.each(frappe.route_options, function(key, value) {
			if($.isArray(value)) {
				me.filter_list.add_filter(me.doctype, key, value[0], value[1]);
			} else {
				me.filter_list.add_filter(me.doctype, key, "=", value);
			}
		});
		frappe.route_options = null;
		me.run();
	},

	run: function(more) {
		// set filter from route
		var route = frappe.get_route();
		var me = this;
		if(route[2]) {
			$.each(frappe.utils.get_args_dict_from_url(route[2]), function(key, val) {
				me.set_filter(key, val, true);
			});
		}
		this.last_updated_on = new Date();
		this._super(more);
	},

	make_no_result: function() {
		var new_button = frappe.boot.user.can_create.indexOf(this.doctype)!=-1
			? ('<hr><p><button class="btn btn-primary" \
				list_view_doc="' + this.doctype + '">'+
				__('Make a new {0}', [__(this.doctype)]) + '</button></p>')
			: '';
		var no_result_message = '<div class="well" style="margin-top: 20px;">\
			<p>' + __("No {0} found", [__(this.doctype)])  + '</p>' + new_button + '</div>';

		return no_result_message;
	},
	render_row: function(row, data) {
		data.doctype = this.doctype;
		this.listview.render(row, data, this);
	},
	get_args: function() {
		var args = {
			doctype: this.doctype,
			fields: this.listview.fields,
			filters: this.filter_list.get_filters(),
			order_by: this.listview.order_by || undefined,
			group_by: this.listview.group_by || undefined,
		}

		// apply default filters, if specified for a listing
		$.each((this.listview.default_filters || []), function(i, f) {
		      args.filters.push(f);
		});

		return args;
	},
	assigned_to_me: function() {
		this.filter_list.add_filter(this.doctype, "_assign", 'like', '%' + user + '%');
		this.run();
	},
	starred_by_me: function() {
		this.filter_list.add_filter(this.doctype, "_starred_by", 'like', '%' + user + '%');
		this.run();
	},
	init_minbar: function() {
		var me = this;
		this.$page.on("click", ".list-tag-preview", function() { me.toggle_tags(); });
		return;

		if(this.can_delete || this.listview.settings.selectable) {
			this.appframe.add_icon_btn("2", 'icon-ok', __('Select All'), function() {
				me.$page.find('.list-delete').prop("checked",
					me.$page.find('.list-delete:checked').length ? false : true);
			});
			this.appframe.add_icon_btn("2", 'icon-trash', __('Delete'),
				function() { me.delete_items(); });
		}
		if(frappe.model.can_import(this.doctype)) {
			this.appframe.add_icon_btn("2", "icon-upload", __("Import"), function() {
				frappe.set_route("data-import-tool", {
					doctype: me.doctype
				})
			});
		}
		if(frappe.model.can_set_user_permissions(this.doctype)) {
			this.appframe.add_icon_btn("2", "icon-shield",
				__("User Permissions Manager"), function() {
					frappe.route_options = {
						doctype: me.doctype
					};
					frappe.set_route("user-permissions");
				});
		}
		if(in_list(user_roles, "System Manager")) {
			this.appframe.add_icon_btn("2", "icon-lock",
				__("Role Permissions Manager"), function() {
					frappe.route_options = {
						doctype: me.doctype
					};
					frappe.set_route("permission-manager");
				});
			this.appframe.add_icon_btn("2", "icon-glass", __("Customize"), function() {
				frappe.set_route("Form", "Customize Form", {
					doctype: me.doctype
				})
			});
		}
	},

	init_star: function() {
		var me = this;
		this.$page.on("click", ".star-action", function() {
			frappe.ui.toggle_star($(this), me.doctype, $(this).attr("data-name"));
		});
	},

	toggle_tags: function() {
		if(this.tags_shown) {
			$(".tag-row").addClass("hide");
			this.tags_shown=false;
		} else {
			$(".tag-row").removeClass("hide");
			this.tags_shown=true;
		}
	},

	get_checked_items: function() {
		return $.map(this.$page.find('.list-delete:checked'), function(e) {
			return $(e).parents(".list-row:first").data('data');
		});
	},

	delete_items: function() {
		var me = this;
		var dl = this.get_checked_items();
		if(!dl.length)
			return;

		frappe.confirm(__('This is permanent action and you cannot undo. Continue?'),
			function() {
				me.set_working(true);
				return frappe.call({
					method: 'frappe.desk.reportview.delete_items',
					args: {
						items: $.map(dl, function(d, i) { return d.name }),
						doctype: me.doctype
					},
					callback: function() {
						me.set_working(false);
						me.dirty = true;
						me.refresh();
					}
				})
			}
		);
	},
	init_stats: function() {
		var me = this;
		this.sidebar_stats = new frappe.views.ListSidebar({
			doctype: this.doctype,
			stats: this.listview.stats,
			parent: $('<div>').appendTo(this.$page.find('.layout-side-section')),
			set_filter: function(fieldname, label) {
				me.set_filter(fieldname, label);
			},
			doclistview: this
		})
	},
	set_filter: function(fieldname, label, no_run) {
		var filter = this.filter_list.get_filter(fieldname);
		if(filter) {
			var v = cstr(filter.field.get_parsed_value());
			if(v.indexOf(label)!=-1) {
				// already set
				return false;
			} else {
				// second filter set for this field
				if(fieldname=='_user_tags' || fieldname=="_starred_by") {
					// and for tags
					this.filter_list.add_filter(this.doctype, fieldname, 'like', '%' + label);
				} else {
					// or for rest using "in"
					filter.set_values(this.doctype, fieldname, 'in', v + ', ' + label);
				}
			}
		} else {
			// no filter for this item,
			// setup one
			if(fieldname=='_user_tags' || fieldname=="_starred_by") {
				this.filter_list.add_filter(this.doctype, fieldname, 'like', '%' + label);
			} else {
				this.filter_list.add_filter(this.doctype, fieldname, '=', label);
			}
		}
		if(!no_run)
			this.run();
	}
});
