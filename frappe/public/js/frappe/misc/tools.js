// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.tools");

frappe.tools.downloadify = function(data, roles, me) {
	if(roles && roles.length && !has_common(roles, user_roles)) {
		msgprint(__("Export not allowed. You need {0} role to export.", [frappe.utils.comma_or(roles)]));
		return;
	}

	var _get_data = function() { return frappe.tools.to_csv(data); };
	var flash_disabled = (navigator.mimeTypes["application/x-shockwave-flash"] == undefined);

	var download_from_server = function() {
		open_url_post("/", {
			args: { data: data, filename: me.title },
			cmd: "frappe.utils.csvutils.send_csv_to_client"
		}, true);
	}

	// save file > abt 200 kb using server call
	if((_get_data().length > 200000) || flash_disabled) {
		download_from_server();
	} else {
		frappe.require("assets/frappe/js/lib/downloadify/downloadify.min.js");
		frappe.require("assets/frappe/js/lib/downloadify/swfobject.js");

		var id = frappe.dom.set_unique_id();
		var msgobj = msgprint($.format('<p id="{0}"></p><hr><a id="alternative-download">{1}</a>',[
					id, __('Alternative download link')]));
		msgobj.$wrapper.find("#alternative-download").on("click", function() { download_from_server(); });

		Downloadify.create(id ,{
			filename: function(){
				return me.title + '.csv';
			},
			data: _get_data,
			swf: 'assets/frappe/js/lib/downloadify/downloadify.swf',
			downloadImage: 'assets/frappe/js/lib/downloadify/download.png',
			onComplete: function(){
				$(msgobj.msg_area).html("<p>Saved</p>")
			},
			onCancel: function(){ msgobj.hide(); },
			onError: function(){ msgobj.hide(); },
			width: 100,
			height: 30,
			transparent: true,
			append: false
		});
	}
};

frappe.markdown = function(txt) {
	if(!frappe.md2html) {
		frappe.require('assets/frappe/js/lib/markdown.js');
		frappe.md2html = new Showdown.converter();
	}

	while(txt.substr(0,1)==="\n") {
		txt = txt.substr(1);
	}

	// remove leading tab (if they exist in the first line)
	var whitespace_len = 0,
		first_line = txt.split("\n")[0];

	while([" ", "\n", "\t"].indexOf(first_line.substr(0,1))!== -1) {
		whitespace_len++;
		first_line = first_line.substr(1);
	}

	if(whitespace_len && whitespace_len != first_line.length) {
		var txt1 = [];
		$.each(txt.split("\n"), function(i, t) {
			txt1.push(t.substr(whitespace_len));
		})
		txt = txt1.join("\n");
	}

	return frappe.md2html.makeHtml(txt);
}


frappe.tools.to_csv = function(data) {
	var res = [];
	$.each(data, function(i, row) {
		row = $.map(row, function(col) {
			return typeof(col)==="string" ? ('"' + col.replace(/"/g, '""') + '"') : col;
		});
		res.push(row.join(","));
	});
	return res.join("\n");
};

frappe.slickgrid_tools = {
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
					!in_list(frappe.model.std_fields_list, col.docfield.fieldname) ) {
					frappe.call({
						method:"frappe.client.make_width_property_setter",
						args: {
							doc: {
								doctype:'Property Setter',
								doctype_or_field: 'DocField',
								doc_type: col.docfield.parent,
								field_name: col.docfield.fieldname,
								property: 'width',
								value: col.width,
								"__islocal": 1
							}
						}
					});
					col.previousWidth = col.width;
					col.docfield.width = col.width;
				}
			});
		});
	}
};
