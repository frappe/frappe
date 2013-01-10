wn.provide("wn.tools");

wn.tools.downloadify = function(data, roles, me) {
	if(roles && roles.length && !has_common(roles, user_roles)) {
		msgprint("Export not allowed. You need " + wn.utils.comma_or(roles)
			+ " Role to export.");
		return;
	}
	wn.require("lib/js/lib/downloadify/downloadify.min.js");
	wn.require("lib/js/lib/downloadify/swfobject.js");
	
	var id = wn.dom.set_unique_id();
	var msgobj = msgprint('<p id="'+ id +'">You must have Flash 10 installed to \
		download this file.</p>');
	
	Downloadify.create(id ,{
		filename: function(){
			return me.title + '.csv';
		},
		data: function(){ 
			return wn.to_csv(data);
		},
		swf: 'lib/js/lib/downloadify/downloadify.swf',
		downloadImage: 'lib/js/lib/downloadify/download.png',
		onComplete: function(){ msgobj.hide(); },
		onCancel: function(){ msgobj.hide(); },
		onError: function(){ msgobj.hide(); },
		width: 100,
		height: 30,
		transparent: true,
		append: false			
	});	
}

wn.to_csv = function(data) {
	var res = [];
	$.each(data, function(i, row) {
		row = $.map(row, function(col) {
			return typeof(col)==="string" ? ('"' + col.replace(/"/g, '""') + '"') : col;
		});
		res.push(row.join(","));
	});
	return res.join("\n");
}

wn.slickgrid_tools = {
	get_view_data: function(columns, dataView, filter) {
		var col_row = $.map(columns, function(v) { return v.name; });
		var res = [];
		var col_map = $.map(columns, function(v) { return v.field; });

		for (var i=0, len=dataView.getLength(); i<len; i++) {
			var d = dataView.getItem(i);
			var row = [];
			$.each(col_map, function(i, col) {
				var val = d[col];
				if(val===null || val===undefined) {
					val = "";
				}
				row.push(val);
			});
			
			if(!filter || filter(row, d)) {
				res.push(row);				
			}
		}
		return [col_row].concat(res);
	},
	add_property_setter_on_resize: function(grid) {
		grid.onColumnsResized.subscribe(function(e, args) {
			$.each(grid.getColumns(), function(i, col) {
				if(col.docfield && col.previousWidth != col.width && 
					!in_list(wn.model.std_fields_list, col.docfield.fieldname) ) {
					wn.call({
						method:"webnotes.client.make_width_property_setter",
						args: {
							doclist: [{
								doctype:'Property Setter',
								doctype_or_field: 'DocField',
								doc_type: col.docfield.parent,
								field_name: col.docfield.fieldname,
								property: 'width',
								value: col.width,
								"__islocal": 1		
							}]
						}
					})
					col.previousWidth = col.width;
					col.docfield.width = col.width;
				}
			});
		});
	}	
}