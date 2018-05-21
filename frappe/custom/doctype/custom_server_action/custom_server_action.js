frappe.custom_server_action = {
	setup_fieldname_select: function(frm) {
		// get the doctype to update fields
		if(!frm.doc.document_type && !frm.doc.target_document_type) {
			return;
		}

		frappe.model.with_doctype(frm.doc.document_type, function() {
			let get_select_options = function(df) {
				return {value: df.fieldname, label: df.fieldname + " (" + __(df.label) + ")"};
			};

			let get_date_change_options = function() {
				let date_options = $.map(fields, function(d) {
					return (d.fieldtype=="Date" || d.fieldtype=="Datetime")?
						get_select_options(d) : null;
				});
				// append creation and modified date to Date Change field
				return date_options.concat([
					{ value: "creation", label: `creation (${__('Created On')})` },
					{ value: "modified", label: `modified (${__('Last Modified Date')})` }
				]);
			};

			let fields = frappe.get_doc("DocType", frm.doc.document_type).fields;
			let options = $.map(fields,
				function(d) { return in_list(frappe.model.no_value_type, d.fieldtype) ?
					null : get_select_options(d); });

			let link_field_options = $.map(fields,
				function(d) { return d.fieldtype =='Link' && d.options == frm.doc.target_document_type ?
					get_select_options(d):null; });

			// set value changed options
			frm.set_df_property("value_changed", "options", [""].concat(options));
			
			// set link field options
			frm.set_df_property("link_field", "options", [""].concat(link_field_options));
							

			// set date changed options
			frm.set_df_property("date_changed", "options", get_date_change_options());

		});
		if (frm.doc.target_document_type){
			frappe.model.with_doctype(frm.doc.target_document_type, function() {
				let get_select_options = function(df) {
					return {value: df.fieldname, label: df.fieldname + " (" + __(df.label) + ")"};
				}

				let fields = frappe.get_doc("DocType", frm.doc.target_document_type).fields;
			
				let options = $.map(fields,
					function(d) { return in_list(frappe.model.no_value_type, d.fieldtype) ?
						null : get_select_options(d); });
			
				// set crud field options
				frappe.meta.get_docfield("Custom Server Action Field", "doc_field", frm.doc.name).options = [""].concat(options);

				frm.fields_dict.value_mapping.grid.refresh();
			});
		}

	}
}

frappe.ui.form.on("Custom Server Action", {
	onload: function(frm) {
		frm.set_query("document_type", function() {
			return {
				"filters": {
					"istable": 0
				}
			}
		});
		frm.set_query("print_format", function() {
			return {
				"filters": {
					"doc_type": frm.doc.document_type
				}
			}
		});
	},
	refresh: function(frm) {
		frappe.custom_server_action.setup_fieldname_select(frm);
		frm.trigger('event');
	},
	document_type: function(frm) {
	if(!frm.doc.target_document_type) {
			frm.set_value('target_document_type', frm.doc.document_type);
		}
		frappe.custom_server_action.setup_fieldname_select(frm);
		
	},

	target_document_type: function(frm){
	    if(!frm.doc.target_document_type) {
			return;
		}
		frappe.custom_server_action.setup_fieldname_select(frm);
	},
	action_type: function(frm){
	    if(frm.doc.action_type != 'Execute Python Code') {
			frm.set_value('code', '');
		}              	    
	},
	view_properties: function(frm) {
		frappe.route_options = {doc_type:frm.doc.document_type};
		frappe.set_route("Form", "Customize Form");
	},
	event: function(frm) {
		if(in_list(['Days Before', 'Days After'], frm.doc.event)) {
			frm.add_custom_button(__('Get Custom Server Actions for Today'), function() {
				frappe.call({
					method: 'frappec.custom.doctype.custom_server_action.custom_server_action.get_documents_for_today',
					args: {
						custom_server_action: frm.doc.name
					},
					callback: function(r) {
						if(r.message) {
							frappe.msgprint(r.message);
						} else {
							frappe.msgprint(__('No custom server action for today'));
						}
					}
				});
			});
		}
	}
});
