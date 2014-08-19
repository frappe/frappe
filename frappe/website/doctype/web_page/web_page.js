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
	refresh: function(doc) {
		cur_frm.cscript.layout(doc);
		cur_frm.set_intro("");
		if(cur_frm.doc.template_path) {
			cur_frm.set_read_only();
		}
		if (!doc.__islocal && doc.published) {
			cur_frm.set_intro(__("Published on website at: {0}",
				[repl('<a href="/%(website_route)s" target="_blank">/%(website_route)s</a>', doc.__onload)]));
		}
	},
	insert_style: function(doc) {
		cur_frm.cscript.layout(doc);
	},
	insert_code: function(doc) {
		cur_frm.cscript.layout(doc);
	}
});
