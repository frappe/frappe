// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Data Import Mapping', {
	onload: function(frm) {
		frm.set_query('document_type', function() {
			return {
				filters: {
					'allow_import': 1
				}
			};
		});
	},
	refresh: function(frm) {
		if (frm.doc.import_file && frm.doc.document_type) {
			frm.trigger('import_file');
			frm.trigger('set_field_options');
		}
	},
	document_type: function(frm) {
		frm.trigger('set_field_options');
	},
	import_file: function(frm) {
		frm.call({
			method: 'get_preview_from_template',
			args: {
				'doctype': frm.doc.document_type,
				'file_path': frm.doc.import_file
			}
		}).then(r => {
			let columns = r.message.reduce(function (result, column) {
				if (typeof column.index != 'undefined') {
					result.push({
						'label': column.header_title,
						'value': column.index
					});
				}
				return result;
			}, []);
			frappe.meta.get_docfield("Data Import Mapping Detail", "column", frm.doc.name).options = [""].concat(columns);
			frm.set_df_property('column', 'options', columns);
		});
	},
	set_field_options(frm) { 
		frappe.model.with_doctype(frm.doc.document_type, function() {
			// Add don't import value
			let fields = [{
				label: `Don't Import`,
				value: `Don't Import`
			}];
			let child_fields = [];
			frappe.get_meta(frm.doc.document_type).fields.map(function(d) {
				if (frappe.model.no_value_type.indexOf(d.fieldtype) === -1 || d.fieldtype == 'Table') {
					if (d.fieldtype == 'Table') {
						frappe.get_meta(d.options).fields.map(function(c) {
							if (frappe.model.no_value_type.indexOf(c.fieldtype) === -1) {
								child_fields.push({
									label: `${c.label} ( ${c.fieldtype} ) - ${c.parent}`,
									value: d.fieldname + '.' + c.fieldname
								});
							}
						});
					} else {
						fields.push({
							label: `${d.label} ( ${d.fieldtype} ) - ${d.parent}`,
							value: d.fieldname
						});
					}
				}
			});

			frappe.meta.get_docfield("Data Import Mapping Detail", "field", frm.doc.name).options = [""].concat(fields, child_fields);
			frm.set_df_property('field', 'options', fields);
		});
	}
});
