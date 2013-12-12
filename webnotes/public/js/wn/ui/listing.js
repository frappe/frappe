// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
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
			if(wn.boot.profile.can_create.indexOf(this.opts.new_doctype)==-1) {
				this.opts.new_doctype = null;
			} else {
				this.opts.new_doctype = this.opts.new_doctype;
			}
		}
		if(!this.opts.no_result_message) {
			this.opts.no_result_message = wn._('Nothing to show');
		}
		this.opts._more = wn._("More");
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
				<div class="list-filters" style="display: none;">\
					<div class="show_filters" style="display: none;">\
						<div class="filter_area"></div>\
						<div>\
							<button class="btn btn-info search-btn">\
								<i class="icon-refresh icon-white"></i> \
								<span class="hidden-phone">Search</span></button>\
							<button class="btn btn-default add-filter-btn">\
								<i class="icon-plus"></i> \
								<span class="hidden-phone">Add Filter</span></button>\
						</div>\
					</div>\
				</div>\
				\
				<div style="margin-bottom:9px" class="list-toolbar-wrapper">\
					<div class="list-toolbar btn-group" style="display:inline-block; margin-right: 10px;">\
					</div>\
					<div style="display: none; width: 24px; margin-left: 4px">\
						<img src="assets/webnotes/images/ui/button-load.gif" \
						class="img-load"/></div>\
				</div><div style="clear:both"></div>\
				\
				<div class="no-result" style="display: none;">\
					%(no_result_message)s\
				</div>\
				\
				<div class="result">\
					<div class="result-list"></div>\
				</div>\
				\
				<p class="paging-button" style="text-align: center;">\
					<button class="btn btn-default btn-more" style="display: none; margin: 15px 0px;">%(_more)s...</div>\
				</p>\
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
			$button = $('<button class="btn btn-default"></button>')
				.appendTo(this.$w.find('.list-toolbar'))
				.html((icon ? ("<i class='"+icon+"'></i> ") : "") + label)
				.click(click);
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
			if(this.appframe) {
				this.appframe.set_title_right("<i class='icon-plus'></i> New", function() { 
					(me.custom_new_doc || me.make_new_doc).apply(me, [me.new_doctype]); });
			}
			this.add_button(wn._('New'), function() { 
				(me.custom_new_doc || me.make_new_doc).apply(me, [me.new_doctype]);
			}, 'icon-plus');
		} 
		
		// hide-filter
		if(me.show_filters) {
			this.add_button(wn._('Filter'), function() {
				me.filter_list.show_filters();
			}, 'icon-search').addClass('btn-filter');
		}
		
		if(me.no_toolbar || me.hide_toolbar) {
			me.$w.find('.list-toolbar-wrapper').toggle(false);
		}
	},
	
	make_new_doc: function(doctype) {
		var me = this;
		wn.model.with_doctype(doctype, function() {
			var doc = wn.model.get_new_doc(doctype);
			if(me.filter_list) {
				$.each(me.filter_list.get_filters(), function(i, f) {
					if(f[0]===doctype && f[2]==="=" && f[1]!=="name")
						doc[f[1]]=f[3];
				})
			}
			wn.set_route("Form", doctype, doc.name);
		});
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
	run: function(more) {
		var me = this;
		if(!more) {
			this.start = 0;
			if(this.onreset) this.onreset();
		}
			
		if(!me.opts.no_loading)
			me.set_working(true);
			
		return wn.call({
			method: this.opts.method || 'webnotes.widgets.query_builder.runquery',
			type: "GET",
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
		
		this.$w.find('.btn-more').toggle(false);

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
						: wn._("Nothing to show"));
						
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
		if(data.keys) {
			var values = [];
			$.each(data.values, function(row_idx, row) {
				var new_row = {};
				$.each(data.keys, function(key_idx, key) {
					new_row[key] = row[key_idx];
				})
				values.push(new_row);
			});
			return values;
		} else {
			return data;
		}
	},

	render_list: function(values) {		
		var m = Math.min(values.length, this.page_length);
		this.data = values;
		if(this.filter_list)
			this.filter_values = this.filter_list.get_filters();
		
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
	},
	set_filter: function(fieldname, label, doctype) {
		if(!doctype) doctype = this.doctype;
		var filter = this.filter_list.get_filter(fieldname);
		if(filter) {
			var v = filter.field.get_parsed_value();
			if(v.indexOf(label)!=-1) {
				// already set
				return false;
			} else {
				// second filter set for this field
				if(fieldname=='_user_tags') {
					// and for tags
					this.filter_list.add_filter(doctype, fieldname, 
						'like', '%' + label);
				} else {
					// or for rest using "in"
					filter.set_values(doctype, fieldname, 'in', v + ', ' + label);
				}
			}
		} else {
			// no filter for this item,
			// setup one
			if(['_user_tags', '_comments'].indexOf(fieldname)!==-1) {
				this.filter_list.add_filter(doctype, fieldname, 
					'like', '%' + label);
			} else {
				this.filter_list.add_filter(doctype, fieldname, '=', label);
			}
		}
	}	
});