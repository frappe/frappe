cur_frm.cscript.refresh = function (doc) {
	if (user!="Administrator") {
		if (doc.standard == 'Yes') {
			cur_frm.toggle_enable(["html", "doc_type", "module"], false);
			cur_frm.disable_save();
		} else {
			cur_frm.toggle_enable(["html", "doc_type", "module"], true);
			cur_frm.enable_save();
		}

		cur_frm.toggle_enable("standard", false);
	}
}
