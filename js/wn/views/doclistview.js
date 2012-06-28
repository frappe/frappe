// Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
// 
// MIT License (MIT)
// 
// Permission is hereby granted, free of charge, to any person obtaining a 
// copy of this software and associated documentation files (the "Software"), 
// to deal in the Software without restriction, including without limitation 
// the rights to use, copy, modify, merge, publish, distribute, sublicense, 
// and/or sell copies of the Software, and to permit persons to whom the 
// Software is furnished to do so, subject to the following conditions:
// 
// The above copyright notice and this permission notice shall be included in 
// all copies or substantial portions of the Software.
// 
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
// INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
// PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
// HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
// CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
// OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
// 

wn.provide('wn.views.doclistview');
wn.provide('wn.doclistviews');

wn.views.doclistview.show = function(doctype) {
	var page_name = wn.get_route_str();
	if(wn.pages[page_name]) {
		wn.container.change_to(wn.pages[page_name]);
	} else {
		var route = wn.get_route();
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
		this.label = get_doctype_label(doctype);
		this.label = (this.label.toLowerCase().substr(-4) == 'list') ?
		 	this.label : (this.label + ' List');
		this.make_page();
		this.setup();
	},
	
	make_page: function() {
		var me = this;
		var page_name = wn.get_route_str();
		var page = wn.container.add_page(page_name);
		wn.container.change_to(page_name);
		this.$page = $(page);
		
		this.$page.html('<div class="layout-wrapper layout-wrapper-background">\
			<div class="appframe-area"></div>\
			<div class="layout-main-section">\
				<div class="wnlist-area"><div class="help">Loading...</div></div>\
			</div>\
			<div class="layout-side-section">\
				<div class="show-docstatus hide" style="margin-bottom: 19px">\
					<h4>Show</h4>\
					<div><input data-docstatus="0" type="checkbox" checked="checked" /> Drafts</div>\
					<div><input data-docstatus="1" type="checkbox" checked="checked" /> Submitted</div>\
					<div><input data-docstatus="2" type="checkbox" /> Cancelled</div>\
				</div>\
			</div>\
			<div style="clear: both"></div>\
		</div>');
		
		this.appframe = new wn.ui.AppFrame(this.$page.find('.appframe-area'));
		wn.views.breadcrumbs($('<span class="breadcrumb-area">').appendTo(this.appframe.$titlebar), 
			locals.DocType[this.doctype].module, this.doctype);
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
		me.make_report_button();
		me.add_delete_option();
	},
	make_report_button: function() {
		var me = this;
		if(wn.boot.profile.can_get_report.indexOf(this.doctype)!=-1) {
			this.appframe.add_button('Build Report', function() {
				wn.set_route('Report2', me.doctype);
			}, 'icon-th')
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
		if(this.meta.__listjs) {
			eval(this.meta.__listjs);
			this.listview = new wn.doclistviews[this.doctype](this);
		} else {
			this.listview = new wn.views.ListView(this);
		}
		this.listview.parent = this;
		this.wrapper = this.$page.find('.wnlist-area');
		this.page_length = 20;
		this.allow_delete = true;
	},
	init_list: function(auto_run) {
		var me = this;
		// init list
		this.make({
			method: 'webnotes.widgets.doclistview.get',
			get_args: this.get_args,
			parent: this.wrapper,
			start: 0,
			page_length: this.page_length,
			show_filters: true,
			show_grid: true,
			new_doctype: this.doctype,
			allow_delete: this.allow_delete,
			no_result_message: this.make_no_result(),
			columns: this.listview.fields
		});
		
		// make_new_doc can be overridden so that default values can be prefilled
		// for example - communication list in customer
		$(this.wrapper).find('button[list_view_doc="'+me.doctype+'"]').click(function(){
			me.make_new_doc(me.doctype);
		});
		
		if((auto_run !== false) && (auto_run !== 0)) this.run();
	},
	
	make_no_result: function() {
		var no_result_message = repl('<div class="well">\
		<p>No %(doctype_label)s found</p>\
		%(description)s\
		<hr>\
		<p><button class="btn btn-info btn-small" list_view_doc="%(doctype)s">\
			Make a new %(doctype_label)s</button>\
		</p></div>', {
			doctype_label: get_doctype_label(this.doctype),
			doctype: this.doctype,
			description: wn.markdown(locals.DocType[this.doctype].description || ''),
		});
		
		return no_result_message;
	},
	render_row: function(row, data) {
		data.doctype = this.doctype;
		this.listview.render(row, data, this);
	},	
	get_query_fields: function() {
		return this.listview.fields;
	},
	get_args: function() {
		return {
			doctype: this.doctype,
			fields: this.get_query_fields(),
			filters: this.filter_list.get_filters(),
			docstatus: this.can_submit ? $.map(this.$page.find('.show-docstatus :checked'), 
				function(inp) { return $(inp).attr('data-docstatus') }) : [],
			order_by: this.listview.order_by || undefined,
		}
	},
	add_delete_option: function() {
		var me = this;
		if(this.can_delete) {
			this.add_button('Delete', function() { me.delete_items(); }, 'icon-remove')
		}
	},
	delete_items: function() {
		var me = this;				
		var dl = $.map(me.$page.find('.list-delete:checked'), function(e) {
			return $(e).data('name');
		});
		if(!dl.length) 
			return;
		if(!confirm('This is PERMANENT action and you cannot undo. Continue?')) {
			return;
		}
		
		me.set_working(true);
		wn.call({
			method: 'webnotes.widgets.doclistview.delete_items',
			args: {
				items: dl,
				doctype: me.doctype
			},
			callback: function() {
				me.set_working(false);
				me.refresh();
			}
		})
	},
	init_stats: function() {
		var me = this
		wn.call({
			method: 'webnotes.widgets.doclistview.get_stats',
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
					$('<button class="btn btn-small"><i class="refresh"></i> Refresh</button>')
						.click(function() {
							me.reload_stats();
						}).appendTo($('<div class="stat-wrapper">')
							.appendTo(me.$page.find('.layout-side-section')))					
				}
				
			}
		});
	},
	render_stat: function(field, stat) {
		var me = this;
		
		if(!stat || !stat.length) {
			if(field=='_user_tags') {
				this.$page.find('.layout-side-section')
					.append('<div class="stat-wrapper"><h4>Tags</h4>\
						<div class="help small"><i>No records tagged.</i><br><br> \
						To add a tag, open the document and click on \
						"Add Tag" on the sidebar</div></div>');
			}
			return;
		}
		
		var label = wn.meta.docfield_map[this.doctype][field] ? 
			wn.meta.docfield_map[this.doctype][field].label : field;
		if(label=='_user_tags') label = 'Tags';
		
		// grid
		var $w = $('<div class="stat-wrapper">\
			<h4>'+ label +'</h4>\
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
		args.width = flt(v[1]) / max * 100;
		args.count = v[1];
		args.field = field;
		
		$item = $(repl('<div class="stat-item">\
			<div class="stat-bar" style="width: %(width)s%"></div>\
			<div class="stat-label">\
				<a href="#" data-label="%(label)s" data-field="%(field)s">\
					%(label)s</a> \
				(%(count)s)</div>\
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
	set_filter: function(fieldname, label) {
		var filter = this.filter_list.get_filter(fieldname);
		if(filter) {
			var v = filter.field.get_value();
			if(v.indexOf(label)!=-1) {
				// already set
				return false;
			} else {
				// second filter set for this field
				if(fieldname=='_user_tags') {
					// and for tags
					this.filter_list.add_filter(fieldname, 'like', '%' + label);
				} else {
					// or for rest using "in"
					filter.set_values(fieldname, 'in', v + ', ' + label);
				}
			}
		} else {
			// no filter for this item,
			// setup one
			if(fieldname=='_user_tags') {
				this.filter_list.add_filter(fieldname, 'like', '%' + label);					
			} else {
				this.filter_list.add_filter(fieldname, '=', label);					
			}
		}
		this.run();
	}
});

wn.views.ListView = Class.extend({
	init: function(doclistview) {
		this.doclistview = doclistview;
		this.doctype = doclistview.doctype;
		
		var t = "`tab"+this.doctype+"`.";
		this.fields = [t + 'name', t + 'owner', t + 'docstatus', 
			t + '_user_tags', t + 'modified'];
		this.stats = ['_user_tags'];
		this.show_hide_check_column();

	},
	columns: [
		{width: '3%', content:'check'},
		{width: '4%', content:'avatar'},
		{width: '3%', content:'docstatus', css: {"text-align": "center"}},
		{width: '35%', content:'name'},
		{width: '40%', content:'tags', css: {'color':'#aaa'}},
		{width: '15%', content:'modified', css: {'text-align': 'right', 'color':'#222'}}		
	],
	render_column: function(data, parent, opts) {
		var me = this;
		
		// style
		if(opts.css) {
			$.each(opts.css, function(k, v) { $(parent).css(k, v)});
		}
		
		// multiple content
		if(opts.content.indexOf && opts.content.indexOf('+')!=-1) {
			$.map(opts.content.split('+'), function(v) {
				me.render_column(data, parent, {content:v});
			});
			return;
		}
		
		// content
		if(typeof opts.content=='function') {
			opts.content(parent, data);
		}
		else if(opts.content=='name') {
			$(parent).append(repl('<a href="#!Form/%(doctype)s/%(name)s">%(name)s</a>', data));
		} 
		else if(opts.content=='avatar') {
			$(parent).append(repl('<span class="avatar-small"><img src="%(avatar)s" \
				title="%(fullname)s"/></span>', 
				data));			
		}
		else if(opts.content=='check') {
			$(parent).append('<input class="list-delete" type="checkbox">');
			$(parent).find('input').data('name', data.name);			
		}
		else if(opts.content=='docstatus') {
			$(parent).append(repl('<span class="docstatus"><i class="%(docstatus_icon)s" \
				title="%(docstatus_title)s"></i></span>', data));			
		}
		else if(opts.content=='tags') {
			this.add_user_tags(parent, data);
		}
		else if(opts.content=='modified') {
			$(parent).append(data.when);			
		}
		else if(opts.type=='bar-graph') {
			args = {
				percent: data[opts.content],
				fully_delivered: (data[opts.content] > 99 ? 'bar-complete' : ''),
				label: opts.label
			}
			$(parent).append(repl('<span class="bar-outer" style="width: 30px; float: right" \
				title="%(percent)s% %(label)s">\
				<span class="bar-inner %(fully_delivered)s" \
					style="width: %(percent)s%;"></span>\
			</span>', args));
		}
		else if(opts.type=='link' && opts.doctype) {
			$(parent).append(repl('<a href="#!Form/'+opts.doctype+'/'
				+data[opts.content]+'">'+data[opts.content]+'</a>', data));
		}
		else if(opts.template) {
			$(parent).append(repl(opts.template, data));
		}
		else if(data[opts.content]) {
			$(parent).append(' ' + data[opts.content]);
		}
		
	},
	render: function(row, data) {
		var me = this;
		this.prepare_data(data);
		rowhtml = '';
				
		// make table
		$.each(this.columns, function(i, v) {
			rowhtml += repl('<td style="width: %(width)s"></td>', v);
		});
		var tr = $(row).html('<table><tbody><tr>' + rowhtml + '</tr></tbody></table>').find('tr').get(0);
		
		// render cells
		$.each(this.columns, function(i, v) {
			me.render_column(data, tr.cells[i], v);
		});
	},
	prepare_data: function(data) {
		data.fullname = wn.user_info(data.owner).fullname;
		data.avatar = wn.user_info(data.owner).image;
		
		this.prepare_when(data, data.modified);
		
		// docstatus
		if(data.docstatus==0 || data.docstatus==null) {
			data.docstatus_icon = 'icon-pencil';
			data.docstatus_title = 'Editable';
		} else if(data.docstatus==1) {
			data.docstatus_icon = 'icon-lock';			
			data.docstatus_title = 'Submitted';
		} else if(data.docstatus==2) {
			data.docstatus_icon = 'icon-remove';			
			data.docstatus_title = 'Cancelled';
		}
		
		// nulls as strings
		for(key in data) {
			if(data[key]==null) {
				data[key]='';
			}
		}
	},
	
	prepare_when: function(data, date_str) {
		if (!date_str) date_str = data.modified;
		// when
		data.when = dateutil.str_to_user(date_str).split(' ')[0];
		var diff = dateutil.get_diff(dateutil.get_today(), date_str.split(' ')[0]);
		if(diff==0) {
			data.when = dateutil.comment_when(date_str);
		}
		if(diff == 1) {
			data.when = 'Yesterday'
		}
		if(diff == 2) {
			data.when = '2 days ago'
		}
	},
	
	add_user_tags: function(parent, data) {
		var me = this;
		if(data._user_tags) {
			if($(parent).html().length > 0) {
				$(parent).append('<br />');
			}
			$.each(data._user_tags.split(','), function(i, t) {
				if(t) {
					$('<span class="label label-info" style="cursor: pointer; line-height: 200%">' 
						+ strip(t) + '</span>')
						.click(function() {
							me.doclistview.set_filter('_user_tags', $(this).text())
						})
						.appendTo(parent);
				}
			});
		}		
	},
	show_hide_check_column: function() {
		if(!this.doclistview.can_delete) {
			this.columns = $.map(this.columns, function(v, i) { if(v.content!='check') return v });
		}
	}
});

wn.provide('wn.views.RecordListView');
wn.views.RecordListView = wn.views.DocListView.extend({
	init: function(doctype, wrapper, ListView) {
		this.doctype = doctype;
		this.wrapper = wrapper;
		this.listview = new ListView(this);
		this.listview.parent = this;
		this.setup();
	},

	setup: function() {
		var me = this;
		me.page_length = 10;

		$(me.wrapper).empty();

		me.init_list();
	},

	get_args: function() {
		var args = this._super();
		$.each((this.default_filters || []), function(i, f) {
		      args.filters.push(f);
		});
		args.docstatus = args.docstatus.concat((this.default_docstatus || []));
		return args;
	},
});