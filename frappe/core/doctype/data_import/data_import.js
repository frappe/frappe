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
		if(frm.doc.preview_data && frm.doc.docstatus!=1) { 
			frm.events.render_html(frm);
			frm.get_field('selected_row').df.hidden = 0;
			frm.doc.flag_file_preview = 1;
			frm.get_field('import_button').$input.addClass("btn-primary btn-md").removeClass('btn-xs');
		}
	},

	before_save: function(frm) {
		if (frm.doc.flag_file_preview) {
			var column_map = [];
			$(frm.fields_dict.file_preview.wrapper).find("select.column-map" ).each(function(index) {
			   	column_map.push($(this).val());
			});
			if(column_map.length != 0){
				frm.doc.selected_columns = JSON.stringify(column_map);
			}
		}
	},

	// after_save: function(frm) {
	// 	console.log("after save");
	// 	if(frm.doc.preview_data) {
	// 		frm.events.render_html(frm);
	// 		frm.get_field('selected_row').df.hidden = 0;
	// 	}
	// },

	render_html: function(frm) {
		var me = this;
		frappe.model.with_doctype(frm.doc.reference_doctype, function() {
			if(frm.doc.reference_doctype) {
				frm.selected_doctype = frappe.get_meta(frm.doc.reference_doctype).fields;

				$(frm.fields_dict.file_preview.wrapper).empty();
		    	me.preview_data = JSON.parse(frm.doc.preview_data);
		    	me.selected_columns = JSON.parse(frm.doc.selected_columns);
		    	$(frappe.render_template("file_preview", {imported_data: me.preview_data, 
 					fields: frm.selected_doctype, column_map: me.selected_columns}))
					.appendTo(frm.fields_dict.file_preview.wrapper);

		    	me.selected_columns = JSON.parse(frm.doc.selected_columns);
				var count = 0;
				$(frm.fields_dict.file_preview.wrapper).find("select.column-map" )
					.each(function(index) {
						$(this).val(me.selected_columns[count]) 
						count++;
				});
			}
		});
	},

	import_button: function(frm) {
		frm.save();
		if (!frm.doc.import_file) {
			frappe.throw("Attach a file for importing")
		}
		frappe.call({
            method: "frappe.core.doctype.data_import.data_import.insert_into_db",
            args: {
            	"reference_doctype": frm.doc.reference_doctype,
            	"import_file": frm.doc.import_file,
            	"selected_columns": frm.doc.selected_columns,
            	"selected_row": frm.doc.selected_row,
            },
            callback: function(r) {
                if (r.message==true) {
	                frm.doc.docstatus = 1;
	                frm.save();
                }
            }
        });
	}

});