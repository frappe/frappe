wn.views.reportview = {
	show: function(dt, rep_name) {
		wn.require('lib/js/legacy/report.compressed.js');
		dt = get_label_doctype(dt);

		if(!_r.rb_con) {
			// first load
			_r.rb_con = new _r.ReportContainer();
		}

		_r.rb_con.set_dt(dt, function(rb) { 
			if(rep_name) {
				var t = rb.current_loaded;
				rb.load_criteria(rep_name);

				// if loaded, then run
				if((rb.dt) && (!rb.dt.has_data() || rb.current_loaded!=t)) {
					rb.dt.run();
				}
			}

			// show
			if(!rb.forbidden) {
				wn.container.change_to('Report Builder');
			}
		} );
	}
}

wn.views.reportview2 = {
	show: function(dt) {
		var page_name = 'Report-' + dt;
		if(!wn.pages[page_name])
			new wn.views.ReportView(dt);
		else
			wn.container.change_to(page_name);
	}
}

wn.views.ReportView = wn.ui.Listing.extend({
	init: function(doctype) {
		var me = this;
		this.import_slickgrid();
		this.doctype = doctype;
		this.tab_name = '`tab'+doctype+'`';
		
		// list of [column_name, table_name]
		this.columns = [['name'], ['owner'], ['creation'], ['modified']];
		this.page = wn.container.add_page('Report-'+doctype);
		wn.model.with_doctype(doctype, function() {
			me.make_page();
			me.setup();
			me.make_column_picker();
			me.make_export();
		});
	},
	import_slickgrid: function() {
		wn.require('lib/js/lib/slickgrid/slick.grid.css');
		wn.require('lib/js/lib/slickgrid/slick-default-theme.css');
		wn.require('lib/js/lib/slickgrid/jquery.event.drag.min.js');
		wn.require('lib/js/lib/slickgrid/slick.core.js');
		wn.require('lib/js/lib/slickgrid/slick.grid.js');
		wn.dom.set_style('.slick-cell { font-size: 12px; }');
	},
	make_page: function() {
		wn.ui.make_app_page({parent:this.page, title:'Report - ' + this.doctype, single_column:true});
		wn.container.change_to(this.page.label);
	},
	setup: function() {
		
		var me = this;
		this.make({
			appframe: this.page.appframe,
			method: 'webnotes.widgets.doclistview.get',
			get_args: this.get_args,
			parent: $(this.page).find('.layout-main'),
			start: 0,
			page_length: 20,
			show_filters: true,
			show_grid: true,
			new_doctype: this.doctype,
			allow_delete: true,
		});	
		this.run();
	},
	get_args: function() {
		var me = this;
		return {
			doctype: this.doctype,
			fields: $.map(this.columns, 
				function(v) { return (v[1] ? ('`tab' + v[1] + '`') : me.tab_name) + '.' + v[0] }),
			filters: this.filter_list.get_filters(),
			docstatus: ['0','1','2']
		}
	},
	// build columns for slickgrid
	build_columns: function() {
		var me = this;
		return $.map(this.columns, function(c) {
			return {
				id: c[0],
				field: c[0],
				name: (wn.meta.docfield_map[c[1] || me.doctype][c[0]] ? 
					wn.meta.docfield_map[c[1] || me.doctype][c[0]].label : toTitle(c[0])),
				width: 120
			}
		});
		
	},
	render_list: function() {
		//this.gridid = wn.dom.set_unique_id()
		var columns = [{id:'_idx', field:'_idx', name: 'Sr.', width: 40}].concat(this.build_columns());

		// add sr in data
		$.each(this.data, function(i, v) {
			v._idx = i+1;
		});

		var options = {
			enableCellNavigation: true,
			enableColumnReorder: false
		};
		
		var grid = new Slick.Grid(this.$w.find('.result-list')
			.css('border', '1px solid grey')
			.css('height', '500px')
			.get(0), this.data, 
			columns, options);
	},
	make_column_picker: function() {
		var me = this;
		this.column_picker = new wn.ui.ColumnPicker(this);
		this.page.appframe.add_button('Pick Columns', function() {
			me.column_picker.show(me.columns);
		}, 'icon-th-list');
	},
	make_export: function() {
		var me = this;
		if(wn.user.has_role(['Administrator', 'System Manager', 'Data Export'])) {
			this.page.appframe.add_button('Export', function() {
				me.export();
			}, 'icon-download-alt');			
		}
	},
	export: function() {
		var args = this.get_args();
		args.cmd = 'webnotes.widgets.doclistview.export_query'
		open_url_post(wn.request.url, args)
	}
});

wn.ui.ColumnPicker = Class.extend({
	init: function(list) {
		this.list = list;
		this.doctype = list.doctype;
		this.selects = {};
	},
	show: function(columns) {
		wn.require('lib/js/lib/jquery/jquery.ui.sortable.js');
		var me = this;
		if(!this.dialog) {
			this.dialog = new wn.ui.Dialog({
				title: 'Pick Columns',
				width: '400'
			});
		}
		$(this.dialog.body).html('<div class="help">Drag to sort columns</div>\
			<div class="column-list"></div>\
			<div><button class="btn btn-small btn-add"><i class="icon-plus"></i>\
				Add Column</button></div>\
			<hr>\
			<div><button class="btn btn-small btn-info">Update</div>');
		
		// show existing	
		$.each(columns, function(i, c) {
			me.add_column(c);
		});
		
		$(this.dialog.body).find('.column-list').sortable();
		
		// add column
		$(this.dialog.body).find('.btn-add').click(function() {
			me.add_column('name');
		});
		
		// update
		$(this.dialog.body).find('.btn-info').click(function() {
			me.dialog.hide();
			// selected columns as list of [column_name, table_name]
			me.list.columns = [];
			$(me.dialog.body).find('select').each(function() {
				me.list.columns.push([$(this).val(), 
					$(this).find('option:selected').attr('table')]);
			})
			me.list.run();
		});
		
		this.dialog.show();
	},
	add_column: function(c) {
		var w = $('<div style="padding: 5px 5px 5px 35px; background-color: #eee; width: 70%; \
			margin-bottom: 10px; border-radius: 3px; cursor: move;">\
			<a class="close" style="margin-top: 5px;">&times</a>\
			</div>')
			.appendTo($(this.dialog.body).find('.column-list'));
		var fieldselect = new wn.ui.FieldSelect(w, this.doctype);
		fieldselect.$select.css('width', '90%').val(c);
		w.find('.close').click(function() {
			$(this).parent().remove();
		});
	}
});