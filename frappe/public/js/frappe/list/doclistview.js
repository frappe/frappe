// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
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
				if(!frappe.views.doclistview[doctype]) {
					frappe.views.doclistview[doctype] = new frappe.views.DocListView({
						doctype: doctype,
						parent: me.make_page(true, "List/" + doctype)
					});
				} else {
					frappe.container.change_to(frappe.views.doclistview[doctype].page_name);
				}
				me.set_cur_list();
			}
		});
	},
	show: function() {
		this._super();
		this.set_cur_list();
		cur_list && cur_list.refresh();
	},
	set_cur_list: function() {
		var route = frappe.get_route();
		cur_list = frappe.container.page && frappe.container.page.doclistview;
		if(cur_list && cur_list.doctype!==route[1]) {
			// changing...
			cur_list = null;
		}
	}
});

$(document).on("save", function(event, doc) {
	frappe.views.set_list_as_dirty(doc.doctype);
});

frappe.views.set_list_as_dirty = function(doctype) {
	var list_page = "List/" + doctype;
	if(frappe.pages[list_page]) {
		if(frappe.pages[list_page].doclistview)
			frappe.pages[list_page].doclistview.dirty = true;
	}
	var route = frappe.get_route();
	if(route[0]==="List" && route[1]===doctype) {
		setTimeout(function() {
			frappe.pages[list_page].doclistview.run();
		}, 100);
	}
}

frappe.views.DocListView = frappe.ui.Listing.extend({
	init: function(opts) {
		$.extend(this, opts);

		if(!frappe.model.can_read(this.doctype)) {
			frappe.show_not_permitted(frappe.get_route_str());
			return;
		};

		this.label = __(this.doctype);
		this.page_name = "List/" + this.doctype;
		this.dirty = true;
		this.tags_shown = false;
		this.label = (this.label.toLowerCase().substr(-4) == 'list') ?
		 	__(this.label) : (__(this.label) + ' ' + __('List'));
		this.make_page();
		this.setup();

		// refresh on init
		this.refresh();
	},

	make_page: function() {
		var me = this;
		this.parent.doclistview = this;
		this.page = this.parent.page;

		this.$page = $(this.parent).css({"min-height": "400px"});

		$('<div class="frappe-list-area"></div>')
			.appendTo(this.page.main);

		this.page.main.addClass("listview-main-section");
		var module = locals.DocType[this.doctype].module;

		this.page.set_title(__("{0} List", [__(this.doctype)]));
		frappe.breadcrumbs.add(module, this.doctype);
	},

	setup: function() {
		var me = this;
		this.can_delete = frappe.model.can_delete(this.doctype);
		this.meta = locals.DocType[this.doctype];
		this.$page.find('.frappe-list-area').empty(),
		this.setup_listview();
		this.init_list(false);
		this.init_menu();
		this.show_match_help();
		this.init_listview();
		this.setup_filterable();
		this.init_filters();
		this.init_headers();
		this.init_star();
		this.init_select_all();
	},

	init_headers: function() {
		var main = frappe.render_template("list_item_main_head", {
			columns: this.listview.columns,
			right_column: this.listview.settings.right_column,
			_checkbox: ((frappe.model.can_delete(this.doctype) || this.listview.settings.selectable)
				&& !this.listview.no_delete)
		});

		this.list_header = $(frappe.render_template("list_item_row_head", { main:main, list:this.listview }))
			.appendTo(this.page.main.find(".list-headers"));
	},

	init_listview: function() {
		if(this.listview.settings.onload) {
			this.listview.settings.onload(this);
		}
	},

	set_sidebar_height: function() {
		var h_main = this.page.sidebar.height();
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
				var new_filter = me.filter_list.add_filter(me.doctype, f[0], f[1], f.slice(2).join(","));
				if (new_filter) {
					// set it to true if atleast 1 filter is added
					added = true;
				}
			});
			added && me.run();
		});
		this.$page.find(".result-list").on("click", ".list-row-left", function(e) {
			// don't open in case of checkbox, star, filterable
			if ((e.target.className || "").indexOf("filterable")!==-1
				|| (e.target.className || "").indexOf("icon-star")!==-1
				|| e.target.type==="checkbox") {
				return;
			}

			var link = $(this).parent().find("a.list-id").get(0);
			window.location.href = link.href;
			return false;
		});
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
			frappe.utils.set_footnote(this, this.$page.find(".layout-main-section"),
				frappe.render_template("list_permission_footer", {condition_list: match_rules_list}));
			$(this.footnote_area).css({"margin-top":"0px"});
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
		this.init_stats();

		if(this.listview.settings.refresh) {
			this.listview.settings.refresh(this);
		}

		if(frappe.route_options) {
			me.set_route_options();
			me.run();
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
			var doctype = me.doctype;

			// if `Child DocType.fieldname`
			if (key.indexOf(".")!==-1) {
				doctype = key.split(".")[0];
				key = key.split(".")[1];
			}

			if($.isArray(value)) {
				me.filter_list.add_filter(doctype, key, value[0], value[1]);
			} else {
				me.filter_list.add_filter(doctype, key, "=", value);
			}
		});
		frappe.route_options = null;
	},

	run: function(more) {
		// set filter from route
		if(this.listview.settings.before_run) {
			this.listview.settings.before_run(this);
		}

		if(!this.listview.settings.use_route) {
			var route = frappe.get_route();
			var me = this;
			if(route[2]) {
				$.each(frappe.utils.get_args_dict_from_url(route[2]), function(key, val) {
					me.set_filter(key, val, true);
				});
			}
		}

		this.list_header.find(".list-starred-by-me")
			.toggleClass("text-extra-muted not-starred", !this.is_star_filtered());

		this.last_updated_on = new Date();
		this.dirty = false;
		this._super(more);

		if(this.listview.settings.post_render) {
			this.listview.settings.post_render(this);
		}
	},

	make_no_result: function() {
		var new_button = frappe.boot.user.can_create.indexOf(this.doctype)!=-1
			? ('<p><button class="btn btn-default btn-sm" \
				list_view_doc="' + this.doctype + '">'+
				__('Make a new {0}', [__(this.doctype)]) + '</button></p>')
			: '';
		var no_result_message = '<div class="msg-box no-border" style="margin-top: 20px;">\
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
	remove_starred_by_me: function() {
		this.filter_list.get_filter("_starred_by").remove();
	},
	is_star_filtered: function() {
		return this.filter_list.filter_exists(this.doctype, "_starred_by", 'like', '%' + user + '%');
	},
	init_menu: function() {
		var me = this;
		this.$page.on("click", ".list-tag-preview", function() { me.toggle_tags(); });

		this.page.set_secondary_action(__("Refresh"), function() {
			me.run();
		}, "octicon octicon-sync");

		this.page.btn_secondary.addClass("hidden-xs");
		this.page.add_menu_item(__("Refresh"), function() {
			me.run();
		}, "octicon octicon-sync").addClass("visible-xs");

		if(frappe.model.can_import(this.doctype)) {
			this.page.add_menu_item(__("Import"), function() {
				frappe.set_route("data-import-tool", {
					doctype: me.doctype
				});
			}, true);
		}
		if(frappe.model.can_set_user_permissions(this.doctype)) {
			this.page.add_menu_item(__("User Permissions Manager"), function() {
					frappe.route_options = {
						doctype: me.doctype
					};
					frappe.set_route("user-permissions");
				}, true);
		}
		if(in_list(user_roles, "System Manager")) {
			this.page.add_menu_item(__("Role Permissions Manager"), function() {
				frappe.route_options = {
					doctype: me.doctype
				};
				frappe.set_route("permission-manager");
			}, true);
			this.page.add_menu_item(__("Customize"), function() {
				frappe.set_route("Form", "Customize Form", {
					doc_type: me.doctype
				})
			}, true);
		}
	},

	init_star: function() {
		var me = this;
		this.$page.find(".result-list").on("click", ".star-action", function() {
			frappe.ui.toggle_star($(this), me.doctype, $(this).attr("data-name"));
			return false;
		});
		this.list_header.find(".list-starred-by-me").on("click", function() {
			if (me.is_star_filtered()) {
				me.remove_starred_by_me();
			} else {
				me.starred_by_me();
			}
		});
	},

	init_select_all: function() {
		var me = this;

		if(this.can_delete || this.listview.settings.selectable) {
			this.list_header.find(".list-select-all").on("click", function() {
				me.$page.find('.list-delete').prop("checked", $(this).prop("checked"));
				me.toggle_delete();
			});

			this.$page.on("click", ".list-delete", function(event) {
				me.toggle_delete();

				// multi-select using shift key
				var $this = $(this);
				if (event.shiftKey && $this.prop("checked")) {
					var $end_row = $this.parents(".list-row");
					var $start_row = $end_row.prevAll(".list-row")
						.find(".list-delete:checked").last().parents(".list-row");
					if ($start_row) {
						$start_row.nextUntil($end_row).find(".list-delete").prop("checked", true);
					}
				}
			});

			// after delete, hide delete button
			this.$w.on("render-complete", function() {
				me.toggle_delete();
			});
		}
	},

	toggle_delete: function() {
		var me = this;
		if (this.$page.find(".list-delete:checked").length) {
			this.page.set_primary_action(__("Delete"), function() { me.delete_items() },
				"octicon octicon-trashcan");
			this.page.btn_primary.addClass("btn-danger");
		} else {
			this.page.btn_primary.removeClass("btn-danger");
			this.set_primary_action();
		}
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

		frappe.confirm(__('Delete permanently?'),
			function() {
				me.set_working(true);
				return frappe.call({
					method: 'frappe.desk.reportview.delete_items',
					freeze: true,
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
			parent: this.$page.find('.layout-side-section'),
			set_filter: function(fieldname, label) {
				me.set_filter(fieldname, label);
			},
			page: this.page,
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
					me.list_header.find(".list-select-all").prop("checked", false);
					me.run();
				}
			}
		});
	}
});
