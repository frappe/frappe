// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

wn.provide('wn.views.doclistview');
wn.provide('wn.doclistviews');

wn.views.ListFactory = wn.views.Factory.extend({
	make: function(route) {
		var me = this;
		wn.model.with_doctype(route[1], function() {
			new wn.views.DocListView({
				doctype: route[1], 
				page: me.make_page(true)
			});
		});
	}
});

$(document).on("save", function(event, doc) {
	var list_page = "List/" + doc.doctype;
	if(wn.pages[list_page]) {
		if(wn.pages[list_page].doclistview)
			wn.pages[list_page].doclistview.dirty = true;
	}
})

wn.views.DocListView = wn.ui.Listing.extend({
	init: function(opts) {
		$.extend(this, opts)
		this.label = wn._(this.doctype);
		this.dirty = true;
		this.tags_shown = false;
		this.label = (this.label.toLowerCase().substr(-4) == 'list') ?
		 	wn._(this.label) : (wn._(this.label) + ' ' + wn._('List'));
		this.make_page();
		this.setup();
		
		var me = this;
		$(this.page).on("show", function() {
			me.refresh();
		});
	},
	
	make_page: function() {
		var me = this;
		this.page.doclistview = this;
		this.$page = $(this.page).css({"min-height": "400px"});
				
		$('<div class="wnlist-area" style="margin-bottom: 25px;">\
			<div class="help">'+wn._('Loading')+'...</div></div>')
			.appendTo(this.$page.find(".layout-main-section"));
			
		$('<div class="show-docstatus hide side-panel">\
			<h5 class="text-muted">Show</h5>\
			<div class="side-panel-body">\
			<div class="text-muted small"><input data-docstatus="0" type="checkbox" \
				checked="checked" /> '+wn._('Drafts')+'</div>\
			<div class="text-muted small"><input data-docstatus="1" type="checkbox" \
				checked="checked" /> '+wn._('Submitted')+'</div>\
			<div class="text-muted small"><input data-docstatus="2" type="checkbox" \
				/> '+wn._('Cancelled')+'</div></div>\
		</div>')
			.appendTo(this.$page.find(".layout-side-section"));
		
		this.$page.find(".layout-main-section")
			.css({"border-right":"1px solid #d7d7d7"})
			.parent().css({"margin-top":"-15px"});
		this.appframe = this.page.appframe;
		var module = locals.DocType[this.doctype].module;
		
		this.appframe.set_title(wn._(this.doctype) + " " + wn._("List"));
		this.appframe.add_module_icon(module, this.doctype, null, true);
		this.appframe.set_views_for(this.doctype, "list");
	},
	
	setup: function() {
		this.can_delete = wn.model.can_delete(this.doctype);
		this.meta = locals.DocType[this.doctype];
		this.$page.find('.wnlist-area').empty(),
		this.setup_listview();
		this.setup_docstatus_filter();
		this.init_list();
		this.init_stats();
		this.init_minbar();
		this.show_match_help();
		if(this.listview.settings.onload) {
			this.listview.settings.onload(this);
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
		var match_rules = wn.perm.get_match_rule(this.doctype);
		if(keys(match_rules).length) {
			var match_text = []
			$.each(match_rules, function(key, values) {
				if(values.length==0) {
					match_text.push(wn._(wn.meta.get_label(me.doctype, key)) + wn._(" is not set"));
				} else if(values.length) {
					match_text.push(wn._(wn.meta.get_label(me.doctype, key)) + " = " + wn.utils.comma_or(values));
				}
			});
			wn.utils.set_footnote(this, this.$page.find(".layout-main-section"), 
				wn._("Showing only for") + ": " + match_text.join(" & "));
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
		this.listview = wn.views.get_listview(this.doctype, this);
		this.wrapper = this.$page.find('.wnlist-area');
		this.page_length = 20;
		this.allow_delete = true;
	},
	init_list: function(auto_run) {
		var me = this;
		// init list
		this.make({
			method: 'webnotes.widgets.reportview.get',
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
		if(wn.route_options) {
			me.filter_list.clear_filters();
			$.each(wn.route_options, function(key, value) {
				me.filter_list.add_filter(me.doctype, key, "=", value);
			});
			wn.route_options = null;
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
	
	run: function(more) {
		// set filter from route
		var route = wn.get_route();
		var me = this;
		if(route[2]) {
			$.each(wn.utils.get_args_dict_from_url(route[2]), function(key, val) {
				me.set_filter(key, val, true);
			});
		}
		this.last_updated_on = new Date();
		this._super(more);
	},
	
	make_no_result: function() {
		var new_button = wn.boot.profile.can_create.indexOf(this.doctype)!=-1
			? ('<hr><p><button class="btn btn-primary" \
				list_view_doc="%(doctype)s">'+
				wn._('Make a new') + ' %(doctype_label)s</button></p>')
			: '';
		var no_result_message = repl('<div class="well" style="margin-top: 20px;">\
		<p>' + wn._("No") + ' %(doctype_label)s ' + wn._("found") + '</p>' + new_button + '</div>', {
			doctype_label: wn._(this.doctype),
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
		this.appframe.add_icon_btn("2", 'icon-tag', wn._('Show Tags'), function() { me.toggle_tags(); });
		this.wrapper.on("click", ".list-tag-preview", function() { me.toggle_tags(); });
		if(this.can_delete || this.listview.settings.selectable) {
			this.appframe.add_icon_btn("2", 'icon-remove', wn._('Delete'), function() { me.delete_items(); });
			this.appframe.add_icon_btn("2", 'icon-ok', wn._('Select All'), function() { 
				me.$page.find('.list-delete').prop("checked", 
					me.$page.find('.list-delete:checked').length ? false : true);
			});
		}
		if(in_list(user_roles, "System Manager")) {
			var meta = locals.DocType[this.doctype];
			if(meta.allow_import || meta.document_type==="Master") {
				this.appframe.add_icon_btn("2", "icon-upload", wn._("Import"), function() {
					wn.set_route("data-import-tool", {
						doctype: me.doctype
					})
				})
			};
			this.appframe.add_icon_btn("2", "icon-glass", wn._("Customize"), function() {
				wn.set_route("Form", "Customize Form", {
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
			
		wn.confirm(wn._('This is permanent action and you cannot undo. Continue?'),
			function() {
				me.set_working(true);
				return wn.call({
					method: 'webnotes.widgets.reportview.delete_items',
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
		this.sidebar_stats = new wn.views.SidebarStats({
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