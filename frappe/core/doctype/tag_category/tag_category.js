// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt
frappe.ui.form.on('Tag', {
	tag_name:function(frm){
		for (var i = 0 ;i<frm.doc.tags.length;i++){
			frm.doc.tags[i].tag_name = toTitle(frm.doc.tags[i].tag_name)
		}
	}
});
