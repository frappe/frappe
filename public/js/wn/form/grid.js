wn.ui.form.Grid = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.docfields = wn.meta.docfield_list[this.df.options];
		this.docfields.sort(function(a, b)  { return a.idx > b.idx ? 1 : -1 });
		this.make();
	},
	refresh: function() {
		this.make_table();
	},
	make: function() {
		$("<h5>").html(this.df.label).appendTo(this.parent);
		$('<div class="btn-group" style="margin-bottom: 10px;">\
			<button class="btn"><i class="icon-plus"></i> </button>\
			<button class="btn"><i class="icon-remove-sign"></i> </button>\
			<button class="btn"><i class="icon-arrow-up"></i> </button>\
			<button class="btn"><i class="icon-arrow-down"></i> </button>\
		</div>').appendTo(this.parent);
		this.make_table();
	},
	make_table: function() {
		var me = this;
		$(this.parent).find(".grid-row").remove();
		$.each(this.get_data() || [], function(ri, d) {
			new wn.ui.form.GridRow({
				parent: me.parent,
				parent_df: me.df,
				docfields: me.docfields,
				doc: d,
				frm: me.frm
			});
		})
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
	// make_table: function() {
	// 	$(this.parent).find("table").remove();
	// 	this.table = $("<table class='table table-bordered'>\
	// 		<thead></thead>\
	// 	</table>")
	// 		.appendTo(this.parent);
	// 	this.tbody = this.table.find("tbody");
	// 	this.make_table_head();
	// 	this.make_table_rows();
	// },
	// make_table_head: function() {
	// 	var row = $("<tr>").appendTo(this.table.find("thead"))
	// 	$("<th style='width: 40px;'>Sr</th>").appendTo(row);
	// 	$.each(this.docfields || [], function(i, df) {
	// 		$("<th>")
	// 			.html(df.label)
	// 			.css({"width": df.width ? df.width : "110px"})
	// 			.appendTo(row);
	// 	})
	// },
	// make_table_rows: function() {
	// 	var me = this;
	// 	var data = this.get_data();
	// 	
	// 	$.each(data || [], function(ri, d) {
	// 		var row = $("<tr>").appendTo(me.tbody);
	// 		$("<td>" + (ri + 1) + "</td>").appendTo(row);
	// 		$.each(me.docfields || [], function(ci, df) {
	// 			$("<td>")
	// 				.html(wn.format(d[df.fieldname], df, null, d))
	// 				.appendTo(row)
	// 		});
	// 	})
	// },
	// get_field: function(fieldname) {
	// 	return {}
	// }
});

wn.ui.form.GridRow = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.show = false;
		this.make();
	},
	make: function() {
		var me = this;
		var panel = $('<div class="panel grid-row">')
			.appendTo(me.parent)
			.css({"cursor": "pointer"})
			.click(function() {
				me.toggle();
			});
		$('<div class="panel-heading">Row #'+ this.doc.idx +'</div>').appendTo(panel);
		this.row = $('<div class="row">').appendTo(panel)
			.css({"display":"none"});
	},
	toggle: function(show) {
		this.show = show===undefined ? 
			show = !this.show :
			show
		this.row.toggle(this.show);
		this.show ? 
			this.render_form() :
			$(this.row).empty();
	},
	render_form: function() {
		var me = this;
		$.each(me.docfields, function(ci, df) {
			if(!df.hidden) {
				var fieldwrapper = $('<div class="col-span-3" \
					style="height: 60px; overflow: hidden;">').appendTo(me.row);
				var fieldobj = make_field(df, me.parent_df.options, 
					fieldwrapper.get(0), me.frm);
				fieldobj.docname = me.doc.name;
				fieldobj.refresh();
			}
		});
	}
});