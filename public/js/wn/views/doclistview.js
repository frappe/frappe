// Copyright 2013 Web Notes Technologies Pvt Ltd
// License: MIT. See license.txt

wn.provide('wn.views.doclistview');
wn.provide('wn.doclistviews');

wn.views.doclistview.show = function(doctype) {
	var route = wn.get_route();
	var page_name = "List/" + route[1];
	if(wn.pages[page_name]) {
		wn.container.change_to(wn.pages[page_name]);
		if(wn.container.page.doclistview)
			wn.container.page.doclistview.run();
	} else {
		if(route[1]) {
			wn.model.with_doctype(route[1], function(r) {
				if(r && r['403']) {
					return;
				}
				new wn.views.DocListView(route[1]);
			});
		}
	}
}

wn.views.DocListView = wn.ui.Listing.extend({
	init: function(doctype) {
		this.doctype = doctype;
		this.label = wn._(doctype);
		this.label = (this.label.toLowerCase().substr(-4) == 'list') ?
		 	wn._(this.label) : (wn._(this.label) + ' ' + wn._('List'));
		this.make_page();
		this.setup();
	},
	
	make_page: function() {
		var me = this;
		var page_name = "List/" + this.doctype;
		var page = wn.container.add_page(page_name);
		wn.container.change_to(page_name);
		page.doclistview = this;
		this.$page = $(page);

		wn.dom.set_style(".show-docstatus div { font-size: 90%; }");
		
		this.$page.html('<div class="layout-wrapper layout-wrapper-background">\
			<div class="appframe-area"></div>\
			<div class="layout-main-section">\
				<div class="wnlist-area" style="margin-top: -15px;">\
					<div class="help">'+wn._('Loading')+'...</div></div>\
			</div>\
			<div class="layout-side-section">\
				<div class="show-docstatus hide section">\
					<div class="section-head">Show</div>\
					<div><input data-docstatus="0" type="checkbox" \
						checked="checked" /> '+wn._('Drafts')+'</div>\
					<div><input data-docstatus="1" type="checkbox" \
						checked="checked" /> '+wn._('Submitted')+'</div>\
					<div><input data-docstatus="2" type="checkbox" \
						/> '+wn._('Cancelled')+'</div>\
				</div>\
			</div>\
			<div style="clear: both"></div>\
		</div>');
				
		this.appframe = new wn.ui.AppFrame(this.$page.find('.appframe-area'));
		var module = locals.DocType[this.doctype].module;
		
		this.appframe.set_title(wn._(this.doctype) + " " + wn._("List"));
		this.appframe.add_home_breadcrumb();
		this.appframe.add_module_breadcrumb(module);
		this.appframe.add_breadcrumb("icon-list");
		this.appframe.set_views_for(this.doctype, "list");
	},

	setup: function() {
		var me = this;
		me.can_delete = wn.model.can_delete(me.doctype);
		me.meta = locals.DocType[me.doctype];
		me.$page.find('.wnlist-area').empty(),
		me.setup_docstatus_filter();
		me.setup_listview();
		me.init_list();
		me.init_stats();
		me.add_delete_option();
		me.make_help();
		me.show_match_help();
	},
	show_match_help: function() {
		var me = this;
		var match_rules = wn.perm.get_match_rule(this.doctype);
		if(keys(match_rules).length) {
			var match_text = []
			$.each(match_rules, function(key, values) {
				match_text.push(wn._(wn.meta.get_label(me.doctype, key)) + " = " + wn.utils.comma_or(values));
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
		this.can_submit = $.map(locals.DocPerm, function(d) { 
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
			(me.listview.make_new_doc || me.make_new_doc)(me.doctype);
		});
		
		if((auto_run !== false) && (auto_run !== 0)) this.run();
	},
	
	run: function(arg0, arg1) {
		// set filter from route
		var route = wn.get_route();
		var me = this;
		if(route[2]) {
			$.each(wn.utils.get_args_dict_from_url(route[2]), function(key, val) {
				me.set_filter(key, val, true);
			});
		}
		this._super(arg0, arg1);
	},
	
	make_no_result: function() {
		var new_button = wn.boot.profile.can_create.indexOf(this.doctype)!=-1
			? ('<hr><p><button class="btn btn-info" \
				list_view_doc="%(doctype)s">'+
				wn._('Make a new') + ' %(doctype_label)s</button></p>')
			: '';
		var no_result_message = repl('<div class="well">\
		<p>No %(doctype_label)s found</p>' + new_button + '</div>', {
			doctype_label: wn._(this.doctype),
			doctype: this.doctype,
		});
		
		return no_result_message;
	},
	render_row: function(row, data) {
		$(row).css({
			"margin-left": "-15px",
			"margin-right": "-15px"
		});
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
	add_delete_option: function() {
		var me = this;
		if(this.can_delete) {
			this.add_button(wn._('Delete'), function() { me.delete_items(); }, 'icon-remove');
			this.add_button(wn._('Select All'), function() { 
				var checks = me.$page.find('.list-delete');
				checks.attr('checked', $(checks.get(0)).attr('checked') ? false : "checked");
			}, 'icon-ok');
		}
	},
	delete_items: function() {
		var me = this;				
		var dl = $.map(me.$page.find('.list-delete:checked'), function(e) {
			return $(e).data('name');
		});
		if(!dl.length) 
			return;
			
		wn.confirm(wn._('This is permanent action and you cannot undo. Continue?'),
			function() {
				me.set_working(true);
				wn.call({
					method: 'webnotes.widgets.reportview.delete_items',
					args: {
						items: dl,
						doctype: me.doctype
					},
					callback: function() {
						me.set_working(false);
						me.refresh();
					}
				})				
			}
		);
	},
	init_stats: function() {
		var me = this
		wn.call({
			type: "GET",
			method: 'webnotes.widgets.reportview.get_stats',
			args: {
				stats: me.listview.stats,
				doctype: me.doctype
			},
			callback: function(r) {
				// This gives a predictable stats order
				$.each(me.listview.stats, function(i, v) {
					me.render_stat(v, r.message[v]);
				});
				
				// reload button at the end
				if(me.listview.stats.length) {
					$('<button class="btn"><i class="refresh"></i> '+wn._('Refresh')+'</button>')
						.click(function() {
							me.reload_stats();
						}).appendTo($('<div class="stat-wrapper">')
							.appendTo(me.$page.find('.layout-side-section')));
				}
				
			}
		});
	},
	render_stat: function(field, stat) {
		var me = this;
		
		if(!stat || !stat.length) {
			if(field=='_user_tags') {
				this.$page.find('.layout-side-section')
					.append('<div class="stat-wrapper section"><div class="section-head">'
						+wn._('Tags')+'</div>\
						<div class="help small"><i>'+wn._('No records tagged.')+'</i><br><br> '
						+wn._('To add a tag, open the document and click on "Add Tag" on the sidebar')
						+'</div></div>');
			}
			return;
		}
		
		var label = wn.meta.docfield_map[this.doctype][field] ? 
			wn.meta.docfield_map[this.doctype][field].label : field;
		if(label=='_user_tags') label = 'Tags';
		
		// grid
		var $w = $('<div class="stat-wrapper section">\
			<div class="section-head">'+ wn._(label) +'</div>\
			<div class="stat-grid">\
			</div>\
		</div>');
		
		// sort items
		stat = stat.sort(function(a, b) { return b[1] - a[1] });
		var sum = 0;
		$.each(stat, function(i,v) { sum = sum + v[1]; })
		
		// render items
		$.each(stat, function(i, v) { 
			me.render_stat_item(i, v, sum, field).appendTo($w.find('.stat-grid'));
		});
		
		$w.appendTo(this.$page.find('.layout-side-section'));
	},
	render_stat_item: function(i, v, max, field) {
		var me = this;
		var args = {}
		args.label = v[0];
		args._label = wn._(v[0]);
		args.width = flt(v[1]) / max * 100;
		args.count = v[1];
		args.field = field;
		args.bar_style = "";
		
		try { args.bar_style = "bar-" + me.listview.label_style[field][args.label]; } 
		catch(e) { }

		$item = $(repl('<div class="progress">\
				<div class="bar %(bar_style)s" style="width: %(width)s%"></div>\
			</div>\
			<div class="stat-label">\
				<a href="#" data-label="%(label)s" data-field="%(field)s">\
					%(_label)s</a> (%(count)s)\
		</div>', args));
		
		this.setup_stat_item_click($item);
		return $item;
	},
	reload_stats: function() {
		this.$page.find('.layout-side-section .stat-wrapper').remove();
		this.init_stats();
	},
	setup_stat_item_click: function($item) {
		var me = this;
		$item.find('a').click(function() {
			var fieldname = $(this).attr('data-field');
			var label = $(this).attr('data-label');
			me.set_filter(fieldname, label);
			return false;
		});		
	},
	set_filter: function(fieldname, label, no_run) {
		var filter = this.filter_list.get_filter(fieldname);
		if(filter) {
			var v = cstr(filter.field.get_value());
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