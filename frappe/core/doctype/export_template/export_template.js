// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Export Template', {

	onload: function(frm) {
		var doctype_options = "";
		for (var i=0; i < frappe.boot.user.can_import.sort().length; i++) {
			doctype_options = doctype_options + "\n" + frappe.boot.user.can_import[i];
		}
		frm.get_field('reference_doctype').df.options = doctype_options;
		cur_frm.disable_save();
		frm.save();
	},

	refresh: function(frm) {
		if (frm.get_field('download_blank_template').$input) {
			frm.get_field('download_blank_template').$input.addClass("btn-primary");
		}
		if (frm.get_field('download_with_data').$input) {
			frm.get_field('download_with_data').$input.addClass("btn-primary");
		}
	},

	reference_doctype: function(frm) {

		frm.$columns = $(cur_frm.fields_dict.doctype_columns.wrapper).empty();

		frappe.model.with_doctype(frm.doc.reference_doctype, function() {
			if(frm.doc.reference_doctype) {
				// render select columns
				var parent_doctype = frappe.get_doc('DocType', frm.doc.reference_doctype);
				parent_doctype["reqd"] = true;
				var doctype_list = [parent_doctype];
				frappe.meta.get_table_fields(frm.doc.reference_doctype).forEach(function(df) {
					var d = frappe.get_doc('DocType', df.options);
					d["reqd"]=df.reqd;
					doctype_list.push(d);
				});
				$(frappe.render_template("export_template", {doctype_list: doctype_list}))
					.appendTo(frm.$columns.empty());

				frm.$columns.find('.btn-select-all').on('click', function() {
					frm.$columns.find('.select-column-check').prop('checked', true);
				});

				frm.$columns.find('.btn-unselect-all').on('click', function() {
					frm.$columns.find('.select-column-check').prop('checked', false);
				});

				frm.$columns.find('.btn-select-mandatory').on('click', function() {
					frm.$columns.find('.select-column-check').prop('checked', false);
					frm.$columns.find('.select-column-check[data-reqd="1"]').prop('checked', true);
				});
			}
		});
	},

	download_blank_template: function(frm) {
		var get_template_url = '/api/method/frappe.core.doctype.export_template.export_template.get_template';
		open_url_post(get_template_url, frm.events.get_export_params(frm, false));
	},

	download_with_data: function(frm) {
		var get_template_url = '/api/method/frappe.core.doctype.export_template.export_template.get_template';
		open_url_post(get_template_url, frm.events.get_export_params(frm, true));
	},

	get_export_params: function(frm, with_data) {
		var doctype = frm.doc.reference_doctype;
		var columns = {};

		frm.$columns.find('.select-column-check:checked').each(function() {
			var _doctype = $(this).attr('data-doctype');
			var _fieldname = $(this).attr('data-fieldname');
			if(!columns[_doctype]) {
				columns[_doctype] = [];
			}
			columns[_doctype].push(_fieldname);
		});

		return {
			doctype: doctype,
			parent_doctype: doctype,
			select_columns: JSON.stringify(columns),
			with_data: with_data ? 'Yes' : 'No',
			all_doctypes: 'Yes',
			xlsx_format: frm.doc.download_in_xlsx
		}
	}

});
