// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

$.extend(cur_frm.cscript, {
	layout: function(doc) {
		if(!doc.__islocal) {
			if(doc.insert_code) {
				if(!doc.javascript) {
					cur_frm.set_value("javascript", '$(function() { });');
				}
			}
			if(doc.insert_style) {
				if(!doc.css) {
					cur_frm.set_value("css", '#page-'+doc.name+' { }');
				}
			}
		}
	},
	refresh: function(doc) {
		cur_frm.cscript.layout(doc);
		if(cur_frm.doc.template_path) {
			cur_frm.set_read_only();
		}
	},
	insert_style: function(doc) {
		cur_frm.cscript.layout(doc);
	},
	insert_code: function(doc) {
		cur_frm.cscript.layout(doc);
	}
});

frappe.ui.form.on("Route", {
	language: function(frm, cdt, cdn) {
		var d = frappe.model.get_doc(cdt, cdn);
		if (d.language && !d.route) {
			frappe.db.get_value('Translation', {language: d.language, source_name: frm.doc.route || frm.doc.title}, 'target_name', (r) => {
				if (r && r.target_name) {
					frappe.model.set_value(cdt, cdn, 'route', (d.language + '/'+ r.target_name));
				}
				else {
					frappe.model.set_value(cdt, cdn, 'route', (d.language + '/' + __(r.target_name)));
				}
			});
		}
	}
});