// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
// MIT License. See license.txt 

cur_frm.cscript.add_list_breadcrumb = function(appframe) {
	appframe.add_breadcrumb("icon-calendar", "Calendar/Event", "Calendar");
}

cur_frm.cscript.repeat_on = function(doc, cdt, cdn) {
	if(doc.repeat_on==="Every Day") {
		$.each(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"], function(i,v) {
			cur_frm.set_value(v, 1);
		})
	}
}

cur_frm.cscript.refresh = function(doc, cdt, cdn) {

}
