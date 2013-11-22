// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
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
	onload: function() {
		// set query!
		cur_frm.set_query("web_page", "toc", function() {
			return {"filters": {"name": ["!=", cur_frm.doc.name]}};
		});
	},
	refresh: function(doc) {
		cur_frm.cscript.layout(doc);
		if(!doc.__islocal && doc.published) {
			cur_frm.appframe.add_button("View In Website", function() {
				window.open(doc.page_name);
			}, "icon-globe");
		}
	},
	insert_style: function(doc) {
		cur_frm.cscript.layout(doc);		
	},
	insert_code: function(doc) {
		cur_frm.cscript.layout(doc);		
	}
});