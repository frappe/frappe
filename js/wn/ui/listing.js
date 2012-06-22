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

// new re-factored Listing object
// uses FieldGroup for rendering filters
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

wn.provide('wn.ui');
wn.ui.Listing = Class.extend({
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
			if(wn.boot.profile.can_read.indexOf(this.opts.new_doctype)==-1) {
				this.opts.new_doctype = null;
			} else {
				this.opts.new_doctype = get_doctype_label(this.opts.new_doctype);				
			}
		}
		if(!this.opts.no_result_message) {
			this.opts.no_result_message = 'Nothing to show'
		}
	},
	make: function(opts) {
		if(opts) {
			this.opts = opts;
		}
		this.prepare_opts();
		$.extend(this, this.opts);
		
		$(this.parent).html(repl('\
			<div class="wnlist">\
				<h3 class="title hide">%(title)s</h3>\
				\
				<div class="list-filters hide">\
					<div class="show_filters well">\
						<div class="filter_area"></div>\
						<div>\
							<button class="btn btn-small btn-info search-btn">\
								<i class="icon-refresh icon-white"></i> Search</button>\
							<button class="btn btn-small add-filter-btn">\
								<i class="icon-plus"></i> Add Filter</button>\
						</div>\
					</div>\
				</div>\
				\
				<div style="margin-bottom:9px" class="list-toolbar-wrapper">\
					<div class="list-toolbar" style="display:inline-block; margin-right: 10px;">\
					</div>\
					<div style="display:inline-block; width: 24px; margin-left: 4px">\
						<img src="images/lib/ui/button-load.gif" \
						class="img-load"/></div>\
				</div><div style="clear:both"></div>\
				\
				<div class="no-result help hide">\
					%(no_result_message)s\
				</div>\
				\
				<div class="result">\
					<div class="result-list"></div>\
				</div>\
				\
				<div class="paging-button">\
					<button class="btn btn-small btn-more hide">More...</div>\
				</div>\
			</div>\
		', this.opts));
		this.$w = $(this.parent).find('.wnlist');
		this.set_events();
		
		if(this.appframe) {
			this.$w.find('.list-toolbar-wrapper').toggle(false);
		} 
		
		if(this.show_filters) {
			this.make_filters();			
		}
	},
	add_button: function(label, click, icon) {
		if(this.appframe) {
			return this.appframe.add_button(label, click, icon)
		} else {
			$button = $('<button class="btn btn-small"></button>')
				.appendTo(this.$w.find('.list-toolbar'))
			if(icon) {
				$('<i>').addClass(icon).appendTo($button);
			}
			$button.html(label).click(click);
			return $button
		}
	},
	show_view: function($btn, $div, $btn_unsel, $div_unsel) {
		$btn_unsel.removeClass('btn-info');
		$btn_unsel.find('i').removeClass('icon-white');
		$div_unsel.toggle(false);

		$btn.addClass('btn-info');
		$btn.find('i').addClass('icon-white');
		$div.toggle(true);
	},
	set_events: function() {
		var me = this;
	
		// next page
		this.$w.find('.btn-more').click(function() {
			me.run({append: true });
		});
		
		// title
		if(this.title) {
			this.$w.find('h3').html(this.title).toggle(true);
		}
	
		// hide-refresh
		if(!(this.hide_refresh || this.no_refresh)) {
			this.add_button('Refresh', function() {
				me.run();
			}, 'icon-refresh');
			
		}
				
		// new
		if(this.new_doctype) {
			this.add_button('New ' + this.new_doctype, function() { 
				me.make_new_doc(me.new_doctype);
			}, 'icon-plus');
		} 
		
		// hide-filter
		if(me.show_filters) {
			this.add_button('Show Filters', function() {
				me.filter_list.show_filters();
			}, 'icon-search').addClass('btn-filter');
		}
		
		if(me.no_toolbar || me.hide_toolbar) {
			me.$w.find('.list-toolbar-wrapper').toggle(false);
		}
	},
	
	make_new_doc: function(new_doctype) {
		new_doc(new_doctype);
	},

	make_filters: function() {
		this.filter_list = new wn.ui.FilterList({
			listobj: this, 
			$parent: this.$w.find('.list-filters').toggle(true),
			doctype: this.doctype,
			filter_fields: this.filter_fields
		});
	},

	clear: function() {
		this.data = [];
		this.$w.find('.result-list').empty();
		this.$w.find('.result').toggle(true);
		this.$w.find('.no-result').toggle(false);
		this.start = 0;
	},
	run: function() {
		// in old - arguments: 0 = callback, 1 = append
		var me = this;
		var a0 = arguments[0]; var a1 = arguments[1];
		
		if(a0 && typeof a0=='function')
			this.onrun = a0;
		if(a0 && a0.callback)
			this.onrun = a0.callback;
		if(!a1 && !(a0 && a0.append)) 
			this.start = 0;

		me.set_working(true);
		wn.call({
			method: this.opts.method || 'webnotes.widgets.query_builder.runquery',
			args: this.get_call_args(a0),
			callback: function(r) { 
				me.set_working(false);
				me.render_results(r) 
			},
			no_spinner: this.opts.no_loading
		});
	},
	set_working: function(flag) {
		this.$w.find('.img-load').toggle(flag);
	},
	get_call_args: function(opts) {
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
			$.extend(args, this.get_args(opts));
		}
		return args;		
	},
	render_results: function(r) {
		if(this.start==0) this.clear();
		
		this.$w.find('.btn-more').toggle(false);

		if(r.message) r.values = r.message;

		if(r.values && r.values.length) {
			this.data = this.data.concat(r.values);
			this.render_list(r.values);
			this.update_paging(r.values);
		} else {
			if(this.start==0) {
				this.$w.find('.result').toggle(false);
				this.$w.find('.no-result').toggle(true);
			}
		}
		
		// callbacks
		if(this.onrun) this.onrun();
		if(this.callback) this.callback(r);
	},

	render_list: function(values) {		
		var m = Math.min(values.length, this.page_length);
		
		// render the rows
		for(var i=0; i < m; i++) {
			this.render_row(this.add_row(), values[i], this, i);
		}
	},
	update_paging: function(values) {
		if(values.length >= this.page_length) {
			this.$w.find('.btn-more').toggle(true);			
			this.start += this.page_length;
		}
	},
	add_row: function() {
		return $('<div class="list-row">').appendTo(this.$w.find('.result-list')).get(0);
	},
	refresh: function() { 
		this.run(); 
	},
	add_limits: function(query) {
		query += ' LIMIT ' + this.start + ',' + (this.page_length+1);
		return query
	}
});