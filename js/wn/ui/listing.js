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
//   query or get_query (will be deprecated)
//   query_max
//   no_result_message ("No result")
//   page_length (20)
//   filters ([{docfield}, ..])
//   hide_refresh (False)
//   new_doctype
//   [function] render_row(parent, data)
//   [function] onrun
//   no_loading (no ajax indicator)


wn.widgets.Listing = function(opts) {
	this.opts = opts;
	this.page_length = 20;
	this.btns = {};
	this.start = 0;
	var me = this;

	// create place holders for all the elements
	this.make = function(opts) {
		if(this.opts.parent.jquery)
			this.opts.parent = this.opts.parent.get(0);
		this.wrapper = $a(this.opts.parent, 'div');
		this.filters_area = $a(this.wrapper, 'div', 'listing-filters');
		this.toolbar_area = $a(this.wrapper, 'div', 'listing-toolbar');
		this.results_area = $a(this.wrapper, 'div', 'listing-results');

		this.more_button_area = $a(this.wrapper, 'div', 'listing-more');

		this.no_results_area = $a(this.wrapper, 'div', 'help_box', {display: 'none'}, 
			(this.opts.no_result_message ? this.opts.no_result_message : 'No results'));

		if(opts) this.opts = opts;
		this.page_length = this.opts.page_length ? this.opts.page_length : this.page_length;
		
		this.make_toolbar();
		this.make_filters();
		this.make_more_button();
	}
	
	// make filters using FieldGroup
	this.make_filters = function() {
		if(this.opts.filters) {
			$ds(this.filters_area);
			
			// expand / collapse filters
			
			this.filters = new wn.widgets.FieldGroup(this.filters_area, this.opts.fields);
		}
	}
	
	// make the toolbar
	this.make_toolbar = function() {
		if(!(this.opts.hide_refresh || this.opts.no_refresh)) {
			if(this.opts.title) {
				$a(this.toolbar_area, 'h3', '', 
					{display:'inline-block',marginRight:'15px'}, 
					this.opts.title);
			}
			this.ref_img = $a(this.toolbar_area, 'span', 'link_type', 
				{color:'#888'}, '[refresh]');
			this.ref_img.onclick = function() { me.run(); }
			
			this.loading_img = $a(this.toolbar_area, 'img', 'lib/images/ui/button-load.gif', {display:'none', marginLeft:'3px', marginBottom:'-2px'});	
		}
		
		if(this.opts.new_doctype) {
			this.new_btn = $btn(this.toolbar_area, 
				'New ' + get_doctype_label(this.opts.new_doctype),
				function() { 
					newdoc(me.opts.new_doctype, me.opts.new_doc_onload, me.opts.new_doc_indialog, me.opts.new_doc_onsave); 
				},
				{marginLeft:'7px'});
		}
	}

	// make more button
	// that shows more results when they are displayed
	this.make_more_button = function() {
		this.more_btn = $btn(this.more_button_area, 'More...', 
			function() {
				me.more_btn.set_working();
				me.run(function() { 
					me.more_btn.done_working(); 
				}, 1);
			}, '', 0, 1
		);
		
		$y(this.more_btn.loading_img, {marginBottom:'0px'});
	}

	// clear the results and re-run the query
	this.clear = function() {
		this.results_area.innerHTML = '';
		this.table = null;
		$ds(this.results_area);
		$dh(this.no_results_area);
	}
	
	// callback on the query
	// build the table
	// returns r.values as a table of results
	this.make_results = function(r, rt) {
		if(this.start==0) this.clear();
		
		$dh(this.more_button_area);
		if(this.loading_img) $dh(this.loading_img)
		if(r.message) r.values = r.message;

		if(r.values && r.values.length) {
			this.values = r.values;
			var m = Math.min(r.values.length, this.page_length);
			// render the rows
			for(var i=0; i < m; i++) {
				var row = this.add_row();
				
				// call the show_cell with row, ri, ci, d
				this.opts.render_row(row, r.values[i], this, i);
			}
			// extend start
			this.start += m;
			
			// refreh more button
			if(r.values.length > this.page_length) $ds(this.more_button_area);
			
		} else {
			if(this.start==0) {
				$dh(this.results_area);
				$ds(this.no_results_area);
			}
		}
		
		// callbacks
		if(this.onrun) this.onrun();
		if(this.opts.onrun) this.opts.onrun();
	}
	
	
	// add a results row
	this.add_row = function() {
		return $a(this.results_area, 'div', '', 
			(opts.cell_style ? opts.cell_style : {padding: '3px 0px'}));
	}
	

	// run the query, get the query from 
	// the get_query method of opts
	this.run = function(callback, append) {
		if(callback)
			this.onrun = callback;

		if(!append)
			this.start = 0;

		// load query
		if(!this.opts.method) {
			this.query = this.opts.get_query ? this.opts.get_query() : this.opts.query;
			this.add_limits();
			var args={ 
				query_max: this.query_max || this.opts.query_max || '',
				as_dict: 1
			}
			args.simple_query = this.query;
		} else {
			var args = {
				limit_start: this.start,
				limit_page_length: this.page_length
			}
		}
		
		if(this.opts.args)
			$.extend(args, this.opts.args)
		
		// show loading
		if(this.loading_img) $di(this.loading_img);
		wn.call({
			method: this.opts.method || 'webnotes.widgets.query_builder.runquery',
			args: args,
			callback: function(r, rt) { me.make_results(r, rt) },
			no_spinner: this.opts.no_loading,
			btn: this.opts.run_btn
		});
	}
	
	this.refresh = this.run;
	
	this.add_limits = function() {
		this.query += ' LIMIT ' + this.start + ',' + (this.page_length+1);
	}
	
	if(opts) this.make();
}