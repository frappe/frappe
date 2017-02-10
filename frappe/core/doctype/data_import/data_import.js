// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Data Import', {

	onload: function(frm) {
		var doctype_options = "";
		for (var i=0; i < frappe.boot.user.can_import.sort().length; i++) {
            doctype_options = doctype_options + "\n" + frappe.boot.user.can_import[i];
        }
		frm.get_field('reference_doctype').df.options = doctype_options;
		frm.doc.flag_file_preview = 0;
	},

	refresh: function(frm) {

	},

	before_save: function(frm) {
		if (frm.doc.flag_file_preview) {
			console.log("i am in saving column");
			var column_map = [];
			$(frm.fields_dict.file_preview.wrapper).find("select.column-map" ).each(function(index) {
			   	column_map.push($(this).val());
			});
			if(column_map.length != 0){
				frm.doc.selected_columns = JSON.stringify(column_map);
			}
		}
	},

	after_save: function(frm) {
		if(frm.doc.preview_data) {
			frm.events.render_html(frm);
			frm.get_field('selected_row').df.hidden = 0;

		}
	},

	render_html: function(frm) {
		var me = this;

		frappe.model.with_doctype(frm.doc.reference_doctype, function() {
				if(frm.doc.reference_doctype) {
					frm.selected_doctype = frappe.get_meta(frm.doc.reference_doctype).fields;
					//frm.doc.reference_doctype = frm.selected_doctype;
				}
		});

		$(frm.fields_dict.file_preview.wrapper).empty();
    	me.preview_data = JSON.parse(frm.doc.preview_data);
    	me.selected_columns = JSON.parse(frm.doc.selected_columns);

    	if (frm.selected_doctype) {
			$(frappe.render_template("file_preview", {imported_data: me.preview_data, 
	 			fields: frm.selected_doctype, column_map: me.selected_columns}))
				.appendTo(frm.fields_dict.file_preview.wrapper);    		
    	}

    	me.selected_columns = JSON.parse(frm.doc.selected_columns);
		var count = 0;
		$(frm.fields_dict.file_preview.wrapper).find("select.column-map" )
			.each(function(index) {
				$(this).val(me.selected_columns[count]) 
				count++;
		});
		frm.doc.flag_file_preview = 1;
	},

	import_file_as: function(frm) {
		var me = this;
		frappe.call({
                method: "frappe.core.doctype.data_import.data_import.process_file",
                args: {
                },
                callback: function(r) {
                }
            });
		console.log("import_file");
	}

});