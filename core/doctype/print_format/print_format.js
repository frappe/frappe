cur_frm.cscript.refresh = function(doc, dt, dn) {
	if(user!="Administrator") {
		if(doc.standard == 'Yes') {
			cur_frm.toggle_enable(["html", "doc_type", "module"], false);
			cur_frm.disable_save();
		}

		cur_frm.toggle_enable("standard", false);
	}
}