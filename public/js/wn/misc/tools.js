wn.markdown = function(txt) {
	if(!wn.md2html) {
		wn.require('lib/js/lib/showdown.js');
		wn.md2html = new Showdown.converter();
	}
	return wn.md2html.makeHtml(txt);
}

wn.downloadify = function(data, roles) {
	if(roles && roles.length && !has_common(roles, user_roles)) {
		msgprint("Export not allowed. You need " + wn.utils.comma_or(roles)
			+ " Role to export.");
		return;
	}
	wn.require("lib/js/lib/downloadify/downloadify.min.js");
	wn.require("lib/js/lib/downloadify/swfobject.js");
	
	var id = wn.dom.set_unique_id();
	var msgobj = msgprint('<p id="'+ id +'">You must have Flash 10 installed to download this file.</p>');
	
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

wn.slickgrid_tools = {
	get_view_data: function(columns, dataView) {
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

			res.push(row);
		}
		return [col_row].concat(res);
			
	}
}