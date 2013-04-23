wn.ui.form.Grid = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.docfields = wn.meta.docfield_list[this.df.options];
		this.docfields.sort(function(a, b)  { return a.idx > b.idx ? 1 : -1 });
		this.make();
	},
	make: function() {
		var me = this;
		
		this.wrapper = $('<div>\
		<div class="panel">\
			<div class="panel-heading"></div>\
			<div class="rows"></div>\
		</div>\
		<div class="btn-group" style="margin-bottom: 10px;">\
			<button class="btn grid-add-row"><i class="icon-plus"></i> Add Row</button>\
		</div>\
		</div>').appendTo(this.parent);

		$(this.wrapper).find(".grid-add-row").click(function() {
			wn.model.add_child(me.frm.doc, me.df.options, me.df.fieldname);
			me.refresh();
		})
		
		this.make_head();
	},
	make_head: function() {
		// labels
		new wn.ui.form.GridRow({
			parent: $(this.parent).find(".panel-heading"),
			parent_df: this.df,
			docfields: this.docfields,
			frm: this.frm
		});	
	},
	refresh: function() {
		var me = this,
			$rows = $(me.parent).find(".rows");	
		
		$rows.find(".grid-row").remove();

		$.each(this.get_data() || [], function(ri, d) {
			new wn.ui.form.GridRow({
				parent: $rows,
				parent_df: me.df,
				docfields: me.docfields,
				doc: d,
				frm: me.frm,
				grid: me
			});
		});
		this.make_sortable($rows);
	},
	make_sortable: function($rows) {
		var me =this;
		$rows.sortable({
			update: function(event, ui) {
				$rows.find(".grid-row").each(function(i, item) {
					var doc = $(item).data("doc");
					doc.idx = i + 1;
					$(this).find(".row-index").html(i + 1);
					me.frm.dirty();
				})
			}
		});
	},
	get_data: function() {
		var data = wn.model.get(this.df.options, {
			"parenttype": this.frm.doctype, 
			"parentfield": this.df.fieldname,
			"parent": this.frm.docname
		});
		data.sort(function(a, b) { return a.idx > b.idx ? 1 : -1 });
		return data;
	},
	set_column_disp: function() {
		// return
	},
	get_field: function(fieldname) {
		return {};
	},
});

wn.ui.form.GridRow = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.show = false;
		this.make();
	},
	make: function() {
		var me = this;
		this.wrapper = $('<div class="grid-row">\
			<div class="header">\
				<div class="row"></div>\
				<div class="toolbar" style="display: none; height: 40px;">\
					Editing Row #<span class="row-index"></span>\
					<button class="btn pull-right" style="margin-left: 7px;">\
						<i class="icon-ok"></i></button>\
					<button class="btn pull-right" style="margin-left: 7px;">\
						<i class="icon-plus"></i></button>\
					<button class="btn btn-danger pull-right"><i class="icon-trash"></i></button>\
				</div>\
			</div>\
			<div class="form-area" style="display: none;"></div>\
		</div>').appendTo(this.parent);

		if(this.doc) {
			this.wrapper.css({
				"margin-bottom": "10px",
				"cursor": "pointer", 
			})
			.find(".row-index").html(this.doc.idx)
		}

		if(me.doc) {
			this.wrapper.find(".header")
				.click(function() {
					me.toggle();
				});
		}
		this.toolbar = this.wrapper.find(".toolbar");
		this.row = this.wrapper.find(".row");
		this.form_area = this.wrapper.find(".form-area");
		this.wrapper.find(".btn-danger").click(function() {
			me.wrapper.fadeOut(function() {
				wn.model.clear_doc(me.doc.doctype, me.doc.name);
				me.frm.dirty();
				me.grid.refresh();
			});
			return false;
		})

		this.make_columns();
		if(this.doc) {
			this.set_data();
		}
	},
	make_columns: function() {
		var me = this,
			total_colsize = 1;
		me.row.empty();
		col = $('<div class="col-span-1 row-index">' + (me.doc ? me.doc.idx : "#")+ '</div>')
			.appendTo(me.row)
		$.each(me.docfields, function(ci, df) {
			if(!df.hidden && !df.print_hide) {
				var colsize = 2;
				switch(df.fieldtype) {
					case "Text":
						colsize = 3;
						break;
					case "Check":
						colsize = 1;
						break;
				}
				total_colsize += colsize
				if(total_colsize > 12) 
					return false;
				$('<div class="col-span-'+colsize+'">' 
					+ (me.doc ? me.doc[df.fieldname] : df.label)+ '</div>')
					.appendTo(me.row)
			}
		});
	},
	toggle: function(show) {
		this.show = show===undefined ? 
			show = !this.show :
			show
		this.form_area.toggle(this.show);
		this.toolbar.toggle(this.show);

		this.row.toggle(!this.show);
		this.wrapper.toggleClass("alert");

		this.show ? 
			this.render_form() :
			$(this.form_area).empty();
		this.make_columns();
	},
	render_form: function() {
		var me = this,
			cnt = 0;
			
		$.each(me.docfields, function(ci, df) {
			if(!df.hidden) {
				if(cnt % 4==0)
					form_row = $('<div class="row">').appendTo(me.form_area);
					
				var fieldwrapper = $('<div class="col-span-3">').appendTo(form_row);
				var fieldobj = make_field(df, me.parent_df.options, 
					fieldwrapper.get(0), me.frm);
				fieldobj.docname = me.doc.name;
				fieldobj.refresh();
				fieldobj.input &&
					$(fieldobj.input).css({"max-height": "60px"});
				cnt++;
			}
		});
	},
	set_data: function() {
		this.wrapper.data({
			"doc": this.doc
		})
	}
});