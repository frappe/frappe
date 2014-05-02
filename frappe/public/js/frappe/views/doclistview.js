// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.views.doclistview');
frappe.provide('frappe.doclistviews');

frappe.views.ListFactory = frappe.views.Factory.extend({
	make: function(route) {
		var me = this;
		frappe.model.with_doctype(route[1], function() {
			if(locals["DocType"][route[1]].issingle) {
				frappe.set_re_route("Form", route[1]);
			} else {
				new frappe.views.DocListView({
					doctype: route[1],
					page: me.make_page(true)
				});
			}
		});
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

		$('<div class="show-docstatus hide side-panel">\
			<h5 class="text-muted">Show</h5>\
			<div class="side-panel-body">\
			<div class="text-muted small"><input data-docstatus="0" type="checkbox" \
				checked="checked" /> '+__('Drafts')+'</div>\
			<div class="text-muted small"><input data-docstatus="1" type="checkbox" \
				checked="checked" /> '+__('Submitted')+'</div>\
			<div class="text-muted small"><input data-docstatus="2" type="checkbox" \
				/> '+__('Cancelled')+'</div></div>\
		</div>')
			.appendTo(this.$page.find(".layout-side-section"));

		this.$page.find(".layout-main-section")
			.addClass("listview-main-section")
			.parent().css({"margin-top":"-15px"});
		this.appframe = this.page.appframe;
		var module = locals.DocType[this.doctype].module;

		this.appframe.set_title(__(this.doctype) + " " + __("List"));
		this.appframe.add_module_icon(module, this.doctype, null, true);
		this.appframe.set_title_left(function() { frappe.set_route(frappe.get_module(module).link); });
		this.appframe.set_views_for(this.doctype, "list");
	},

	setup: function() {
		this.can_delete = frappe.model.can_delete(this.doctype);
		this.meta = locals.DocType[this.doctype];
		this.$page.find('.frappe-list-area').empty(),
		this.setup_listview();
		this.setup_docstatus_filter();
		this.init_list(false);
		this.init_stats();
		this.init_minbar();
		this.show_match_help();
		if(this.listview.settings.onload) {
			this.listview.settings.onload(this);
		}
		if(this.listview.settings.set_title_left) {
			this.appframe.set_title_left(this.listview.settings.set_title_left);
		}
		this.make_help();
		this.$page.find(".show_filters").css({"padding":"15px", "margin":"0px -15px"});
		var me = this;
		// this.$w.on("render-complete", function() {
		// 	me.set_sidebar_height();
		// });
	},

	set_sidebar_height: function() {
		var h_main = this.$page.find(".layout-main-section").height();
		var h_side = this.$page.find(".layout-side-section").height();
		if(h_side > h_main)
			this.$page.find(".layout-main-section").css({"min-height": h_side});
	},

	show_match_help: function() {
		var me = this;
		var match_rules = frappe.perm.get_match_rules(this.doctype);
		var perm = frappe.perm.get_perm(this.doctype);

		if(keys(match_rules).length) {
			var match_text = []
			$.each(match_rules, function(key, values) {
				if(values.length==0) {
					match_text.push(__(key) + __(" is not set"));
				} else if(values.length) {
					match_text.push(__(key) + " = " + frappe.utils.comma_or(values));
				}
			});

			if(perm[0].restricted) {
				match_text.push(__("Or Created By") + " = " + user);
			}
			frappe.utils.set_footnote(this, this.$page.find(".layout-main-section"),
				"<p>" + __("Showing only for (if not empty)") + ":</p><ul>"
				+ $.map(match_text, function(txt) { return "<li>"+txt+"</li>" }).join("")) + "</ul>";
			$(this.footnote_area).css({"margin-top":"0px", "margin-bottom":"20px"});
		}
	},
	make_help: function() {
		// Help
		if(this.meta.description) {
			this.appframe.add_help_button(this.meta.description);
		}
	},
	setup_docstatus_filter: function() {
		var me = this;
		this.can_submit = $.map(locals.DocPerm || [], function(d) {
			if(d.parent==me.meta.name && d.submit) return 1
			else return null;
		}).length;
		if(this.can_submit) {
			this.$page.find('.show-docstatus').removeClass('hide');
			this.$page.find('.show-docstatus input').click(function() {
				me.run();
			})
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
			method: 'frappe.widgets.reportview.get',
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
			me.filter_list.add_filter(me.doctype, key, "=", value);
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
				list_view_doc="%(doctype)s">'+
				__('Make a new') + ' %(doctype_label)s</button></p>')
			: '';
		var no_result_message = repl('<div class="well" style="margin-top: 20px;">\
		<p>' + __("No") + ' %(doctype_label)s ' + __("found") + '</p>' + new_button + '</div>', {
			doctype_label: __(this.doctype),
			doctype: this.doctype,
		});

		return no_result_message;
	},
	render_row: function(row, data) {
		data.doctype = this.doctype;
		this.listview.render(row, data, this);
	},
	get_args: function() {
		var docstatus_list = this.can_submit ? $.map(this.$page.find('.show-docstatus :checked'),
			function(inp) {
				return $(inp).attr('data-docstatus');
			}) : []

		var args = {
			doctype: this.doctype,
			fields: this.listview.fields,
			filters: this.filter_list.get_filters(),
			docstatus: docstatus_list,
			order_by: this.listview.order_by || undefined,
			group_by: this.listview.group_by || undefined,
		}

		// apply default filters, if specified for a listing
		$.each((this.listview.default_filters || []), function(i, f) {
		      args.filters.push(f);
		});

		return args;
	},
	init_minbar: function() {
		var me = this;
		this.appframe.add_icon_btn("2", 'icon-tag', __('Show Tags'), function() { me.toggle_tags(); });
		this.wrapper.on("click", ".list-tag-preview", function() { me.toggle_tags(); });
		if(this.can_delete || this.listview.settings.selectable) {
			this.appframe.add_icon_btn("2", 'icon-remove', __('Delete'), function() { me.delete_items(); });
			this.appframe.add_icon_btn("2", 'icon-ok', __('Select All'), function() {
				me.$page.find('.list-delete').prop("checked",
					me.$page.find('.list-delete:checked').length ? false : true);
			});
		}
		if(frappe.model.can_import(this.doctype)) {
			this.appframe.add_icon_btn("2", "icon-upload", __("Import"), function() {
				frappe.set_route("data-import-tool", {
					doctype: me.doctype
				})
			});
		}
		if(frappe.model.can_restrict(this.doctype)) {
			this.appframe.add_icon_btn("2", "icon-shield",
				__("User Permission Restrictions"), function() {
					frappe.route_options = {
						property: me.doctype
					};
					frappe.set_route("user-properties");
				});
		}
		if(in_list(user_roles, "System Manager")) {
			this.appframe.add_icon_btn("2", "icon-glass", __("Customize"), function() {
				frappe.set_route("Form", "Customize Form", {
					doctype: me.doctype
				})
			});
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
			return $(e).data('data');
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
					method: 'frappe.widgets.reportview.delete_items',
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
		this.sidebar_stats = new frappe.views.SidebarStats({
			doctype: this.doctype,
			stats: this.listview.stats,
			parent: this.$page.find('.layout-side-section'),
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
				if(fieldname=='_user_tags') {
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
			if(fieldname=='_user_tags') {
				this.filter_list.add_filter(this.doctype, fieldname, 'like', '%' + label);
			} else {
				this.filter_list.add_filter(this.doctype, fieldname, '=', label);
			}
		}
		if(!no_run)
			this.run();
	}
});
