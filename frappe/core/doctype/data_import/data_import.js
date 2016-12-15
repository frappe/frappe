// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Data Import', {

	onload: function(frm) {
		var doctype_options = "";
		for (var i=0; i < frappe.boot.user.can_import.sort().length; i++) {
            doctype_options = doctype_options + "\n" + frappe.boot.user.can_import[i];
        }
		frm.get_field('reference_doctype').df.options = doctype_options;

	},

	refresh: function(frm) {
		if(frm.doc.preview_data) {
			frm.add_custom_button(__("Import into Database"), function() {
				if (frm.doc.selected_row) {
					var column_map = [];
					$(frm.fields_dict.file_preview.wrapper).find("select.column-map" )
						.each(function(index) {
					   		column_map.push($(this).val());
					});
					frm.doc.selected_columns = JSON.stringify(column_map);
					frappe.msgprint(__("Now save the document"))
					//frm.events.import_file(frm)
				}
				else {
					frappe.throw(__("Select Row to Import from"))
				}
			}).addClass("btn-primary");
			frm.events.render_html(frm);
		}
	},

	check: function(frm) {
		console.log(frm.doc.selected_columns);
		frm.add_custom_button(__("Import into Database"), function() {
				//frm.events.import_file(frm)
			}).addClass("btn-primary");
		
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

		var preview_html = ['<hr><h5>{{ __("Select the docfield to map with the column") }}</h5>\
							<div class="table-responsive">\
  							<table class="table table-bordered table-hover">\
  		 					<caption>{%= __("Imported File Data") %}</caption>\
  							{% for (var i = -1; i < imported_data.length; i++) { %}\
  								<tr>\
								{% if (i == -1) { %}\
  									<td>{%= __("Row No.") %}</td>\
	  								{% for (var j = 0; j < imported_data[0].length; j++) { %}\
									<td>\
									<select class="form-control column-map">\
			        				<option value="" disabled selected>\
			        					{%= __("Select Fieldtype") %}</option>\
									{% for (var k = 0; k < fields.length; k++) { %}\
									<option value="{%= fields[k].fieldname %}">\
										{{ __(fields[k].label) }}</option>\
			        				{% } %}\
									</select>\
									</td>\
									{% } %}\
  								{% } %}\
  								{% if (i != -1) { %}\
  									<td>{{i}}</td>\
	  								{% for (var j = 0; j < imported_data[i].length; j++) { \
										var cell_data = imported_data[i][j] %}\
										<td>{{ cell_data }}</td>\
									{% } %}\
  								{% } %}\
						    	</tr>\
					   		{% } %}\
					  		</table>\
    						</div>'].join("\n");
    	me.preview_data = JSON.parse(frm.doc.preview_data);
    	// console.log(frm.selected_doctype);
    	if (frm.selected_doctype) {
			$(frappe.render(preview_html, {imported_data: me.preview_data, 
	 			fields: frm.selected_doctype})).appendTo(frm.fields_dict.file_preview.wrapper);    		
    	}
	},

	// import: function(frm) {
	// 	var column_map = [];
	// 	$(frm.fields_dict.file_preview.wrapper).find("select.column-map" ).each(function(index) {
	// 	   	column_map.push($(this).val());
	// 	});
	// 	frm.doc.selected_columns = column_map;
	// 	console.log(frm.doc.selected_columns);
		
	// },

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